from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.open_position import (
    OpenPosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

if TYPE_CHECKING:
    # Same circular-import shape `stop_management_policy.py` already
    # documents: `FillPricing` imports `fee_calculator_policy`, which runs
    # this package's own `__init__.py` (which exports this class) — a
    # top-level import here would be circular. Type-only per
    # `code/quality.md` §2's one documented exception.
    from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
        BrokerSimulationConfig,
    )
    from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.fill_pricing import (
        FillPricing,
    )

logger = logging.getLogger("App.PaperExchange")

_ENTRY_LOG_LABEL: dict[PositionSide, str] = {
    PositionSide.LONG: "BUY",
    PositionSide.SHORT: "SHORT",
}
_EXIT_LOG_LABEL: dict[PositionSide, str] = {
    PositionSide.LONG: "SELL",
    PositionSide.SHORT: "COVER",
}


@dataclass(frozen=True)
class PositionOpenRequest:
    """The five values `open_position()` needs beyond the ledger it reads/
    writes (`positions`, `balance`) — bundled per `code/quality.md` §7 rather
    than five separate parameters."""

    side: PositionSide
    price: float
    time: datetime
    reason: str
    metadata: Mapping[str, Any]


class PositionLifecyclePolicy:
    """
    @brief Domain policy for the position entry/exit/trade-recording
    lifecycle: opening a position, closing it (fully or partially), and the
    resulting `Trade` record — the "books" mechanism `paper_exchange.py`'s
    own class docstring names (cash, open positions, the trade log), split
    out once `BOT-144` (this file's own task) found it the last extraction
    target left after `PR #266`'s `StopManagementPolicy` split.
    @details Deliberately kept as one extraction rather than one class per
    method (`_open`/`_close_one_position`/`_close_partial_position`/
    `_apply_partial_take_profits` are one lifecycle at the same abstraction
    level — the Single-Scope Cohesion counterweight, `code/quality.md` §3,
    applies the same way it already does for `StopManagementPolicy`'s own
    three methods).

    Every method here follows the same "return the new state, let the
    caller apply it" idiom `paper_exchange.py`'s own `check_intrabar_stops()`
    already uses for `FillPricing.evaluate_liquidations()`/
    `evaluate_intrabar_stops()` — this policy never mutates the caller's
    `balance` (floats cannot be mutated in place) or replaces its
    `positions` list itself; it returns the values the caller (the ledger
    owner, `PaperExchange`) applies to its own `self._balance`/
    `self._trades`/`self._positions`. It mutates an individual `OpenPosition`
    instance's own fields directly where the original code did (e.g.
    `_close_partial_position`'s in-place quantity reduction) — the same
    established pattern `StopManagementPolicy` already uses on the same
    domain entity, not a new one.

    Constructed once per `PaperExchange` run with the same `FillPricing`/
    `BrokerSimulationConfig`/`symbol` the exchange itself holds — these three
    never change across a run, so injecting them here (rather than passing
    them on every call) keeps each method's own argument count to the
    values that actually vary per call.
    """

    def __init__(
        self,
        symbol: str,
        pricing: FillPricing,
        broker_config: BrokerSimulationConfig,
    ) -> None:
        self._symbol = symbol
        self._pricing = pricing
        self._broker_config = broker_config

    def open_position(
        self,
        positions: list[OpenPosition],
        balance: float,
        request: PositionOpenRequest,
    ) -> tuple[list[OpenPosition], float]:
        """Validates and opens `request`, or rejects it (logged, unchanged
        return) exactly as `paper_exchange.py`'s own former `_open()` did.
        Returns `(positions-with-the-new-entry-appended-or-unchanged,
        resulting-balance)`."""
        side = request.side
        opposite = (
            PositionSide.SHORT if side is PositionSide.LONG else PositionSide.LONG
        )
        if any(pos.side is opposite for pos in positions):
            logger.debug(
                f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} rejected: an opposite-side "
                f"({opposite.value}) position is still open — BOT-050 requires the "
                "strategy to close it first with an explicit signal, never an implicit reversal"
            )
            return positions, balance
        if len(positions) >= self._broker_config.pyramiding:
            logger.debug(
                f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} rejected: pyramiding limit "
                f"reached ({len(positions)}/{self._broker_config.pyramiding})"
            )
            return positions, balance

        current_eq = balance + sum(
            self._pricing.mark_to_market(
                pos.side,
                pos.leverage,
                pos.quantity,
                pos.entry_price,
                pos.balance_before_entry,
                request.price,
            )
            for pos in positions
        )
        capital_deployed, quantity, entry_fee = self._pricing.entry_capital(
            side, request.price, current_eq, balance
        )
        if quantity <= 0 or capital_deployed <= 0:
            logger.debug(
                f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} rejected: insufficient balance "
                f"({balance:,.2f}) for sizing"
            )
            return positions, balance

        effective_price = self._pricing.entry_effective_price(side, request.price)
        stop_loss_price = self._pricing.stop_loss_price(side, effective_price)
        take_profit_price = self._pricing.take_profit_price(side, effective_price)
        leverage = self._pricing.leverage_for(side)
        liquidation_price = self._pricing.liquidation_price(
            side, leverage, effective_price
        )
        partial_tp_prices = self._pricing.partial_take_profit_prices(
            side, effective_price
        )
        partial_tp_close_quantities = tuple(
            quantity * level.close_fraction
            for level in self._broker_config.partial_take_profit_levels
        )

        new_balance = balance - capital_deployed
        position = OpenPosition(
            quantity=quantity,
            entry_price=effective_price,
            entry_time=request.time,
            balance_before_entry=capital_deployed,
            entry_fee=entry_fee,
            entry_reason=request.reason,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            entry_metadata=request.metadata,
            side=side,
            leverage=leverage,
            liquidation_price=liquidation_price,
            partial_take_profit_prices=partial_tp_prices,
            partial_take_profit_close_quantities=partial_tp_close_quantities,
        )
        new_positions = [*positions, position]
        slippage_delta = self._pricing.slippage_delta()
        slip_sign = "+" if side is PositionSide.LONG else "-"
        logger.debug(
            f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} filled | Price: {effective_price:,.2f} "
            f"(raw: {request.price:,.2f}, slip: {slip_sign}{slippage_delta:,.2f}) | "
            f"Qty: {quantity:.6f} | Cost: {capital_deployed:,.2f} | Fee: {entry_fee:,.2f} | "
            f"Pos: {len(new_positions)}/{self._broker_config.pyramiding} | Cash Left: {new_balance:,.2f}"
        )
        return new_positions, new_balance

    def close_one_position(
        self,
        pos: OpenPosition,
        exit_price: float,
        time: datetime,
        exit_reason: ExitReason,
        *,
        raw_price: float | None = None,
        slippage_delta: float = 0.0,
    ) -> tuple[Trade, float]:
        """Closes `pos` in full. Returns `(trade, balance_release)` — the
        caller applies `self._balance += balance_release` and
        `self._trades.append(trade)`."""
        exit_fee = self._pricing.exit_fee(pos.quantity, exit_price)

        pnl, pnl_percent, balance_release = self._pricing.realized_pnl(
            pos.side,
            pos.leverage,
            pos.quantity,
            pos.entry_price,
            exit_price,
            pos.balance_before_entry,
            pos.entry_fee,
            exit_fee,
        )
        if exit_reason is ExitReason.LIQUIDATION:
            pnl, pnl_percent, balance_release = (
                self._pricing.clamp_liquidation_settlement(
                    pnl, pnl_percent, balance_release, pos.balance_before_entry
                )
            )

        trade = Trade(
            symbol=self._symbol,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            exit_time=time,
            exit_price=exit_price,
            quantity=pos.quantity,
            pnl=pnl,
            pnl_percent=pnl_percent,
            fees_paid=pos.entry_fee + exit_fee,
            entry_reason=pos.entry_reason,
            exit_reason=exit_reason,
            metadata=pos.entry_metadata,
            side=pos.side,
            leverage=pos.leverage,
            mae_percent=pos.mae_percent,
            mfe_percent=pos.mfe_percent,
        )
        exit_label = _EXIT_LOG_LABEL[pos.side]
        if raw_price is not None:
            slip_sign = "-" if pos.side is PositionSide.LONG else "+"
            price_detail = (
                f"Price: {exit_price:,.2f} (raw: {raw_price:,.2f}, "
                f"slip: {slip_sign}{slippage_delta:,.2f})"
            )
        else:
            price_detail = f"Price: {exit_price:,.2f}"
        logger.debug(
            f"[paper-exchange] {exit_label} filled | {price_detail} | "
            f"Qty: {pos.quantity:.6f} | PnL: {pnl:+,.2f} ({pnl_percent:+.2f}%) | "
            f"Fee: {pos.entry_fee + exit_fee:,.2f} | Reason: {exit_reason.value}"
        )
        return trade, balance_release

    def close_partial_position(
        self,
        pos: OpenPosition,
        exit_price: float,
        time: datetime,
        close_qty: float,
    ) -> tuple[Trade, float]:
        """
        @brief BOT-105C — closes exactly `close_qty` of `pos` (a scale-out
        level's fixed absolute quantity, already clamped to at most what
        remains), realizes its prorated PnL, and shrinks `pos` in place
        rather than removing it. Returns `(trade, balance_release)`.
        @details `fraction` is computed against `pos.quantity` as it stands
        RIGHT NOW — the remaining quantity after any earlier partial exit —
        so `entry_fee`/`balance_before_entry` are prorated against what
        actually remains, not the original position. `pos.quantity`,
        `pos.entry_fee` and `pos.balance_before_entry` are then all reduced
        by that same fraction, keeping the three mutually consistent for
        whatever exit (partial or, on the final level, full) prorates
        against them next — the same generic contract a full close already
        uses via `close_one_position()`, just with `fraction < 1.0`.
        """
        fraction = close_qty / pos.quantity
        prorated_balance = pos.balance_before_entry * fraction
        prorated_entry_fee = pos.entry_fee * fraction
        exit_fee = self._pricing.exit_fee(close_qty, exit_price)

        pnl, pnl_percent, balance_release = self._pricing.realized_pnl(
            pos.side,
            pos.leverage,
            close_qty,
            pos.entry_price,
            exit_price,
            prorated_balance,
            prorated_entry_fee,
            exit_fee,
        )

        trade = Trade(
            symbol=self._symbol,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            exit_time=time,
            exit_price=exit_price,
            quantity=close_qty,
            pnl=pnl,
            pnl_percent=pnl_percent,
            fees_paid=prorated_entry_fee + exit_fee,
            entry_reason=pos.entry_reason,
            exit_reason=ExitReason.PARTIAL_TAKE_PROFIT,
            metadata=pos.entry_metadata,
            side=pos.side,
            leverage=pos.leverage,
            mae_percent=pos.mae_percent,
            mfe_percent=pos.mfe_percent,
        )

        pos.quantity -= close_qty
        pos.balance_before_entry -= prorated_balance
        pos.entry_fee -= prorated_entry_fee

        logger.debug(
            f"[paper-exchange] Partial take-profit filled | {pos.side.value} "
            f"Price: {exit_price:,.2f} | Qty: {close_qty:.6f} | "
            f"PnL: {pnl:+,.2f} ({pnl_percent:+.2f}%) | "
            f"Remaining: {pos.quantity:.6f}"
        )
        return trade, balance_release

    def apply_partial_take_profits(
        self, positions: list[OpenPosition], high: float, low: float, time: datetime
    ) -> tuple[Sequence[Trade], float, list[OpenPosition]]:
        """
        @brief BOT-105C — checks every still-open position's next pending
        scale-out level against this bar's high/low, in order, closing
        each level hit and advancing past it. Returns
        `(trades, total_balance_release, still-open-positions)`.
        @details Called LAST in `check_intrabar_stops()`, after liquidation
        and stop-loss/take-profit have already removed their own closes
        from the caller's position list — a position that fully closed this
        bar through one of those never also produces a partial-TP trade the
        same bar, the same pessimistic-first convention `BOT-041`/
        `BOT-105B` already apply to an ambiguous SL/TP bar, extended here
        rather than inventing a new tie-break for a same-bar overlap.
        """
        if not positions:
            return [], 0.0, positions
        trades: list[Trade] = []
        total_balance_release = 0.0
        fully_closed: list[OpenPosition] = []
        for pos in positions:
            while pos.partial_tp_next_level_index < len(pos.partial_take_profit_prices):
                idx = pos.partial_tp_next_level_index
                level_price = pos.partial_take_profit_prices[idx]
                hit = (
                    high >= level_price
                    if pos.side is PositionSide.LONG
                    else low <= level_price
                )
                if not hit:
                    break
                close_qty = min(
                    pos.partial_take_profit_close_quantities[idx], pos.quantity
                )
                trade, balance_release = self.close_partial_position(
                    pos, level_price, time, close_qty
                )
                trades.append(trade)
                total_balance_release += balance_release
                pos.partial_tp_next_level_index += 1
                if pos.quantity <= 0:
                    fully_closed.append(pos)
                    break
        if fully_closed:
            # Identity, not `OpenPosition`'s (value) `__eq__` — this file's
            # other position-list rebuilds are all identity-based; `in`
            # here would silently drop an unrelated, still-open,
            # field-identical twin (e.g. two pyramided entries opened at
            # the same price/time).
            fully_closed_ids = {id(p) for p in fully_closed}
            still_open = [p for p in positions if id(p) not in fully_closed_ids]
        else:
            still_open = list(positions)
        return trades, total_balance_release, still_open
