from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.policies.fee_calculator_policy import (
    FeeCalculatorPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.policies.margin_risk_policy import (
    MarginRiskPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.policies.order_matching_policy import (
    IStoppablePosition,
    OrderMatchingPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.domain.value_objects.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
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
#: BOT-105A — a position whose remaining quantity has decayed to at most
#: this (after one or more partial take-profit closes) is treated as fully
#: scaled out, rather than left open holding a float-rounding dust amount.
_QUANTITY_EPSILON = 1e-9


@dataclass
class _OpenPosition(IStoppablePosition):
    quantity: float
    entry_price: float
    entry_time: datetime
    balance_before_entry: float
    entry_fee: float
    entry_reason: str
    entry_metadata: Mapping[str, Any] = field(default_factory=dict)
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    side: PositionSide = PositionSide.LONG
    leverage: float = 1.0
    #: BOT-105A — the position's original size, set once in `_open()` and
    #: never mutated. `quantity` above shrinks as partial take-profit
    #: levels fire; `tp_levels` fractions are of THIS, not of whatever's
    #: currently left open (so "50%, 50%" closes the whole position, not
    #: 50% then 50%-of-the-remaining-50%).
    initial_quantity: float = 0.0
    #: BOT-105A — best price seen since entry (highest for LONG, lowest
    #: for SHORT); drives both break-even and trailing-stop.
    peak_price: float = 0.0
    breakeven_triggered: bool = False
    #: BOT-105A — remaining `(price, size_fraction)` levels, `price`
    #: precomputed from each configured level's `profit_pct` the same way
    #: `take_profit_price` above is (`OrderMatchingPolicy.
    #: calculate_take_profit_price`), sorted nearest-target-first in
    #: `_open()`, popped as each fires.
    tp_levels_remaining: list[tuple[float, float]] = field(default_factory=list)
    #: BOT-105A — which mechanism most recently moved `stop_loss_price`;
    #: reported as the `Trade.exit_reason` if that stop then triggers, so
    #: a ratcheted stop is never misreported as a plain `STOP_LOSS`.
    stop_source: ExitReason = ExitReason.STOP_LOSS


class PaperExchange:
    """
    @brief Simulated broker/exchange for backtesting strategy executions (BOT-021, BOT-041, BOT-050, BOT-104, EPIC-003C).
    @details Orchestrates trade lifecycle, delegating financial calculations to pure Domain Policies:
    - MarginRiskPolicy: margin, leverage, mark-to-market, realized PnL
    - OrderMatchingPolicy: slippage, effective entry/exit prices, intrabar stops
    - FeeCalculatorPolicy: commission calculation on notional/contracts
    """

    def __init__(
        self,
        symbol: str,
        initial_balance: float,
        fee_percent: float = 0.1,
        position_sizing: PositionSizing | None = None,
        broker_config: BrokerSimulationConfig | None = None,
        margin_policy: MarginRiskPolicy | None = None,
        matching_policy: OrderMatchingPolicy | None = None,
        fee_policy: FeeCalculatorPolicy | None = None,
    ) -> None:
        if initial_balance <= 0:
            raise ValueError(f"initial_balance must be positive, got {initial_balance}")
        if fee_percent < 0:
            raise ValueError(f"fee_percent must be >= 0, got {fee_percent}")

        self._symbol = symbol
        self._balance = initial_balance
        self._initial_balance = initial_balance

        if broker_config is not None:
            self._broker_config = broker_config
        else:
            self._broker_config = BrokerSimulationConfig(
                commission_type=CommissionType.PERCENT,
                commission_value=fee_percent,
            )

        if position_sizing is not None:
            self._position_sizing = position_sizing
        else:
            self._position_sizing = PositionSizing(
                type=PositionSizingType.PERCENT_OF_EQUITY,
                value=100.0,
            )

        self._margin_policy = margin_policy or MarginRiskPolicy()
        self._matching_policy = matching_policy or OrderMatchingPolicy()
        self._fee_policy = fee_policy or FeeCalculatorPolicy()

        self._positions: list[_OpenPosition] = []
        self._trades: list[Trade] = []

        logger.info(
            f"[paper-exchange] Initialized for {symbol} | Initial Capital: {initial_balance:,.2f} | "
            f"Sizing: {self._position_sizing.type.value} ({self._position_sizing.value}) | "
            f"Pyramiding: {self._broker_config.pyramiding} | Slippage: {self._broker_config.slippage_ticks} ticks | "
            f"Commission: {self._broker_config.commission_value} ({self._broker_config.commission_type.value})"
        )

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def balance(self) -> float:
        """Available unallocated cash balance."""
        return self._balance

    @property
    def is_in_position(self) -> bool:
        return len(self._positions) > 0

    @property
    def position_count(self) -> int:
        return len(self._positions)

    @property
    def current_side(self) -> PositionSide | None:
        """BOT-110 — the side every currently open position shares, or None when flat."""
        return self._positions[0].side if self._positions else None

    @property
    def trades(self) -> list[Trade]:
        return list(self._trades)

    @property
    def position_sizing(self) -> PositionSizing:
        return self._position_sizing

    @property
    def broker_config(self) -> BrokerSimulationConfig:
        return self._broker_config

    def equity(self, mark_price: float) -> float:
        """Cash balance if flat, or cash balance plus marked-to-market position values."""
        if not self._positions:
            return self._balance
        total_open_value = sum(
            self._margin_policy.mark_to_market(
                pos.side,
                pos.leverage,
                pos.quantity,
                pos.entry_price,
                pos.balance_before_entry,
                mark_price,
            )
            for pos in self._positions
        )
        return self._balance + total_open_value

    def fill(self, signal: Signal, price: float, time: datetime) -> Trade | None:
        """
        Executes signal at price/time.
        Returns the last closed Trade on a SELL/COVER that closed positions, otherwise None.
        """
        if signal.action is SignalAction.BUY:
            self._open(PositionSide.LONG, price, time, signal.reason, signal.metadata)
            return None
        if signal.action is SignalAction.SELL:
            closed = self._close(
                PositionSide.LONG, price, time, ExitReason.STRATEGY_SIGNAL
            )
            return closed[-1] if closed else None
        if signal.action is SignalAction.SHORT:
            self._open(PositionSide.SHORT, price, time, signal.reason, signal.metadata)
            return None
        if signal.action is SignalAction.COVER:
            closed = self._close(
                PositionSide.SHORT, price, time, ExitReason.STRATEGY_SIGNAL
            )
            return closed[-1] if closed else None
        return None

    def force_close(self, price: float, time: datetime) -> Trade | None:
        """
        Realizes every still-open position, either side, at price/time at the end of a backtest run.
        """
        closed = list(
            self._close(PositionSide.LONG, price, time, ExitReason.END_OF_BACKTEST)
        )
        closed += self._close(
            PositionSide.SHORT, price, time, ExitReason.END_OF_BACKTEST
        )
        return closed[-1] if closed else None

    def _slippage_delta(self) -> float:
        return self._matching_policy.calculate_slippage_delta(
            self._broker_config.slippage_ticks, self._broker_config.tick_size
        )

    def _entry_effective_price(self, side: PositionSide, price: float) -> float:
        return self._matching_policy.calculate_entry_effective_price(
            side, price, self._slippage_delta()
        )

    def _exit_effective_price(self, side: PositionSide, price: float) -> float:
        return self._matching_policy.calculate_exit_effective_price(
            side, price, self._slippage_delta()
        )

    def _leverage_for(self, side: PositionSide) -> float:
        return self._margin_policy.get_leverage(
            side,
            self._broker_config.long_leverage,
            self._broker_config.short_leverage,
        )

    def _calculate_entry_capital(
        self, side: PositionSide, price: float, current_equity: float
    ) -> tuple[float, float, float]:
        effective_price = self._entry_effective_price(side, price)
        if effective_price <= 0:
            return 0.0, 0.0, 0.0

        leverage = self._leverage_for(side)
        margin, notional_capital = self._margin_policy.calculate_margin_and_notional(
            side,
            effective_price,
            current_equity,
            self._balance,
            self._position_sizing,
            leverage,
            self._broker_config.stop_loss_pct,
        )

        if margin <= 0 or notional_capital <= 0:
            return 0.0, 0.0, 0.0

        entry_fee, quantity = self._fee_policy.calculate_entry_fee_and_quantity(
            notional_capital,
            effective_price,
            self._broker_config.commission_type,
            self._broker_config.commission_value,
        )

        if quantity <= 0:
            return 0.0, 0.0, 0.0

        return margin, quantity, entry_fee

    def _open(
        self,
        side: PositionSide,
        price: float,
        time: datetime,
        reason: str,
        metadata: Mapping[str, Any],
    ) -> None:
        opposite = (
            PositionSide.SHORT if side is PositionSide.LONG else PositionSide.LONG
        )
        if any(pos.side is opposite for pos in self._positions):
            logger.debug(
                f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} rejected: an opposite-side "
                f"({opposite.value}) position is still open — BOT-050 requires the "
                "strategy to close it first with an explicit signal, never an implicit reversal"
            )
            return
        if len(self._positions) >= self._broker_config.pyramiding:
            logger.debug(
                f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} rejected: pyramiding limit "
                f"reached ({len(self._positions)}/{self._broker_config.pyramiding})"
            )
            return

        current_eq = self.equity(price)
        capital_deployed, quantity, entry_fee = self._calculate_entry_capital(
            side, price, current_eq
        )
        if quantity <= 0 or capital_deployed <= 0:
            logger.debug(
                f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} rejected: insufficient balance "
                f"({self._balance:,.2f}) for sizing {self._position_sizing}"
            )
            return

        effective_price = self._entry_effective_price(side, price)
        stop_loss_price = self._matching_policy.calculate_stop_loss_price(
            side, effective_price, self._broker_config.stop_loss_pct
        )
        # BOT-105A — tp_levels replaces the single take_profit_price
        # mechanism for this position when configured (mutually exclusive,
        # see BrokerSimulationConfig.tp_levels's own docstring).
        if self._broker_config.tp_levels:
            take_profit_price = None
            tp_levels_remaining = []
            for profit_pct, size_fraction in sorted(
                self._broker_config.tp_levels, key=lambda level: level[0]
            ):
                level_price = self._matching_policy.calculate_take_profit_price(
                    side, effective_price, profit_pct
                )
                if level_price is None:
                    # profit_pct comes from a validated BrokerSimulationConfig
                    # tp_levels entry (always a positive float), so
                    # calculate_take_profit_price's None branch (only
                    # reachable when its pct argument is None) is
                    # unreachable here — this only fires on a broken
                    # invariant, not normal operation.
                    raise RuntimeError(
                        f"calculate_take_profit_price returned None for a "
                        f"validated tp_levels profit_pct={profit_pct}"
                    )
                tp_levels_remaining.append((level_price, size_fraction))
        else:
            take_profit_price = self._matching_policy.calculate_take_profit_price(
                side, effective_price, self._broker_config.take_profit_pct
            )
            tp_levels_remaining = []

        self._balance -= capital_deployed
        position = _OpenPosition(
            quantity=quantity,
            entry_price=effective_price,
            entry_time=time,
            balance_before_entry=capital_deployed,
            entry_fee=entry_fee,
            entry_reason=reason,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            entry_metadata=metadata,
            side=side,
            leverage=self._leverage_for(side),
            initial_quantity=quantity,
            peak_price=effective_price,
            tp_levels_remaining=tp_levels_remaining,
        )
        self._positions.append(position)
        slippage_delta = self._slippage_delta()
        slip_sign = "+" if side is PositionSide.LONG else "-"
        logger.debug(
            f"[paper-exchange] {_ENTRY_LOG_LABEL[side]} filled | Price: {effective_price:,.2f} "
            f"(raw: {price:,.2f}, slip: {slip_sign}{slippage_delta:,.2f}) | "
            f"Qty: {quantity:.6f} | Cost: {capital_deployed:,.2f} | Fee: {entry_fee:,.2f} | "
            f"Pos: {len(self._positions)}/{self._broker_config.pyramiding} | Cash Left: {self._balance:,.2f}"
        )

    def _settle_position_slice(
        self,
        pos: _OpenPosition,
        close_quantity: float,
        exit_price: float,
        time: datetime,
        exit_reason: ExitReason,
        *,
        raw_price: float | None = None,
        slippage_delta: float = 0.0,
    ) -> Trade:
        """
        @brief Settles `close_quantity` of `pos` — the whole position for a
        full close, or a slice for a partial one (BOT-105A) — mutating
        `pos` down by exactly that slice.
        @details `MarginRiskPolicy.calculate_realized_pnl()`'s formula
        already generalizes correctly to a slice as long as
        `balance_before_entry`/`entry_fee` passed in are scaled to the same
        fraction as `close_quantity` — a full close is just the fraction
        `close_quantity / pos.quantity == 1.0` case, so this single method
        serves both without any change to that policy's signature. `pos`'s
        own `balance_before_entry`/`entry_fee`/`quantity` are reduced by
        the scaled/closed amounts so a later slice (partial or final) of
        the same position is computed against what's genuinely left, not
        double-counting margin or fees already settled.
        """
        fraction = close_quantity / pos.quantity
        scaled_balance = pos.balance_before_entry * fraction
        scaled_entry_fee = pos.entry_fee * fraction

        exit_fee = self._fee_policy.calculate_exit_fee(
            close_quantity,
            exit_price,
            self._broker_config.commission_type,
            self._broker_config.commission_value,
        )

        pnl, pnl_percent, balance_release = self._margin_policy.calculate_realized_pnl(
            pos.side,
            pos.leverage,
            close_quantity,
            pos.entry_price,
            exit_price,
            scaled_balance,
            scaled_entry_fee,
            exit_fee,
        )
        self._balance += balance_release
        pos.quantity -= close_quantity
        pos.balance_before_entry -= scaled_balance
        pos.entry_fee -= scaled_entry_fee

        trade = Trade(
            symbol=self._symbol,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            exit_time=time,
            exit_price=exit_price,
            quantity=close_quantity,
            pnl=pnl,
            pnl_percent=pnl_percent,
            fees_paid=scaled_entry_fee + exit_fee,
            entry_reason=pos.entry_reason,
            exit_reason=exit_reason,
            metadata=pos.entry_metadata,
            side=pos.side,
        )
        self._trades.append(trade)
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
            f"Qty: {close_quantity:.6f} | PnL: {pnl:+,.2f} ({pnl_percent:+.2f}%) | "
            f"Fee: {scaled_entry_fee + exit_fee:,.2f} | Reason: {exit_reason.value}"
        )
        return trade

    def _close_one_position(
        self,
        pos: _OpenPosition,
        exit_price: float,
        time: datetime,
        exit_reason: ExitReason,
        *,
        raw_price: float | None = None,
        slippage_delta: float = 0.0,
    ) -> Trade:
        """Closes the whole remaining position — a fraction-1.0 slice."""
        return self._settle_position_slice(
            pos,
            pos.quantity,
            exit_price,
            time,
            exit_reason,
            raw_price=raw_price,
            slippage_delta=slippage_delta,
        )

    def _close(
        self,
        side: PositionSide,
        price: float,
        time: datetime,
        exit_reason: ExitReason,
    ) -> Sequence[Trade]:
        matching = [pos for pos in self._positions if pos.side is side]
        if not matching:
            logger.debug(
                f"[paper-exchange] {_EXIT_LOG_LABEL[side]} rejected: no open "
                f"{side.value} positions to close"
            )
            return []

        effective_price = self._exit_effective_price(side, price)
        slippage_delta = self._slippage_delta()

        closed_trades = [
            self._close_one_position(
                pos,
                effective_price,
                time,
                exit_reason,
                raw_price=price,
                slippage_delta=slippage_delta,
            )
            for pos in matching
        ]

        self._positions = [pos for pos in self._positions if pos.side is not side]
        logger.debug(
            f"[paper-exchange] All positions closed "
            f"({len(closed_trades)} trades) | New Balance: {self._balance:,.2f}"
        )
        return closed_trades

    def _update_trailing_and_breakeven(
        self, pos: _OpenPosition, high: float, low: float
    ) -> None:
        """
        @brief Ratchets `pos.stop_loss_price` toward locking in more profit
        as this bar's favorable extreme extends (BOT-105A) — break-even
        moves it to entry once armed; trailing then keeps it a fixed %
        behind the best price seen since entry. Both only ever move the
        stop in the position's favor (never backward), and a no-op when
        neither mechanism is configured — existing behavior for every
        position not using them is unchanged.
        """
        config = self._broker_config
        if (
            config.breakeven_trigger_pct is None
            and config.trailing_activation_pct is None
        ):
            return

        if pos.side is PositionSide.LONG:
            pos.peak_price = max(pos.peak_price, high)
            profit_pct = (pos.peak_price - pos.entry_price) / pos.entry_price * 100.0
        else:
            pos.peak_price = min(pos.peak_price, low)
            profit_pct = (pos.entry_price - pos.peak_price) / pos.entry_price * 100.0

        if (
            config.breakeven_trigger_pct is not None
            and not pos.breakeven_triggered
            and profit_pct >= config.breakeven_trigger_pct
        ):
            pos.breakeven_triggered = True
            favorable = (
                pos.stop_loss_price is None or pos.entry_price > pos.stop_loss_price
                if pos.side is PositionSide.LONG
                else pos.stop_loss_price is None
                or pos.entry_price < pos.stop_loss_price
            )
            if favorable:
                pos.stop_loss_price = pos.entry_price
                pos.stop_source = ExitReason.BREAK_EVEN_STOP

        if (
            config.trailing_activation_pct is not None
            and profit_pct >= config.trailing_activation_pct
        ):
            if config.trailing_offset_pct is None:
                # __post_init__ validates trailing_offset_pct is set
                # whenever trailing_activation_pct is (both or neither) —
                # only reachable on a broken invariant.
                raise RuntimeError(
                    "trailing_activation_pct is set but trailing_offset_pct "
                    "is None — BrokerSimulationConfig validation invariant "
                    "was bypassed"
                )
            offset = config.trailing_offset_pct / 100.0
            if pos.side is PositionSide.LONG:
                candidate = pos.peak_price * (1.0 - offset)
                favorable = (
                    pos.stop_loss_price is None or candidate > pos.stop_loss_price
                )
            else:
                candidate = pos.peak_price * (1.0 + offset)
                favorable = (
                    pos.stop_loss_price is None or candidate < pos.stop_loss_price
                )
            if favorable:
                pos.stop_loss_price = candidate
                pos.stop_source = ExitReason.TRAILING_STOP

    def _settle_tp_levels(
        self, pos: _OpenPosition, high: float, low: float, time: datetime
    ) -> list[Trade]:
        """
        @brief Partially closes `pos` at every configured `tp_levels`
        price reached by this bar's range, nearest-target-first (BOT-105A)
        — a single wide bar can cross more than one level. Relies on
        `pos.tp_levels_remaining` already being sorted nearest-first
        (`_open()`): once one level isn't reached, none of the farther
        ones can be either, so the loop stops at the first miss.
        """
        trades: list[Trade] = []
        while pos.tp_levels_remaining:
            price, size_fraction = pos.tp_levels_remaining[0]
            hit = high >= price if pos.side is PositionSide.LONG else low <= price
            if not hit:
                break
            pos.tp_levels_remaining.pop(0)
            close_quantity = min(pos.initial_quantity * size_fraction, pos.quantity)
            if close_quantity <= 0:
                continue
            trades.append(
                self._settle_position_slice(
                    pos, close_quantity, price, time, ExitReason.PARTIAL_TAKE_PROFIT
                )
            )
            if pos.quantity <= _QUANTITY_EPSILON:
                break
        return trades

    def check_intrabar_stops(
        self, high: float, low: float, time: datetime
    ) -> Sequence[Trade]:
        """
        @brief Checks every open position's stop-loss/take-profit against
        bar high/low boundaries.
        @details BOT-105A: first ratchets every position's trailing/
        break-even stop for this bar (a no-op unless configured — see
        `_update_trailing_and_breakeven`), then evaluates stops. Positions
        with `tp_levels` configured are evaluated separately (SL first —
        same conservative "stop wins" convention `evaluate_intrabar_stops`
        already uses — then partial-TP levels) since that policy method
        only understands the single stop/target pair; every other
        position still goes through it unchanged.
        """
        if not self._positions:
            return []

        for pos in self._positions:
            self._update_trailing_and_breakeven(pos, high, low)

        scaling_positions = [p for p in self._positions if p.tp_levels_remaining]
        plain_positions = [p for p in self._positions if not p.tp_levels_remaining]

        trades: list[Trade] = []

        triggered, still_open_plain = self._matching_policy.evaluate_intrabar_stops(
            plain_positions, high, low
        )
        for pos, exit_price, reason in triggered:
            # A stop hit reports pos.stop_source (STOP_LOSS unless
            # break-even/trailing moved it) — a plain TAKE_PROFIT hit is
            # unaffected by either mechanism.
            actual_reason = (
                pos.stop_source if reason is ExitReason.STOP_LOSS else reason
            )
            trades.append(
                self._close_one_position(pos, exit_price, time, actual_reason)
            )

        still_open_scaling: list[_OpenPosition] = []
        for pos in scaling_positions:
            sl_price = pos.stop_loss_price
            if sl_price is not None:
                stop_hit = (
                    low <= sl_price
                    if pos.side is PositionSide.LONG
                    else high >= sl_price
                )
                if stop_hit:
                    trades.append(
                        self._close_one_position(pos, sl_price, time, pos.stop_source)
                    )
                    continue
            trades.extend(self._settle_tp_levels(pos, high, low, time))
            if pos.quantity > _QUANTITY_EPSILON:
                still_open_scaling.append(pos)

        self._positions = still_open_plain + still_open_scaling
        return trades
