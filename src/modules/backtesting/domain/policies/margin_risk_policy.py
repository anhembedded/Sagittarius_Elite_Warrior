"""`MarginRiskPolicy` — the paper broker's books: leverage by direction,
mark-to-market valuation and PnL realization.

@details It used to allocate capital too, and that method is gone from here:
`EPIC-025` PR 2.1d moved the sizing rule to
`modules/strategy/domain/policies/margin_sizing_policy.py` behind
`strategy.contracts.ISizingPolicy`, because ADR D17 decided *how much to bet*
is the armed strategy's decision and `backtesting` must size a paper fill by
the same rule live trading uses. The formula is unchanged; what changed is
which context owns it. What is left here is what a broker does **after** the
size is known, which is `backtesting`'s own and moves with it in Phase 3.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


@runtime_checkable
class ILiquidatablePosition(Protocol):
    """What `evaluate_liquidations` needs from a position.

    `Protocol` (`architecture-rule.md` §2.1 reason (b), "§2 already forbids a
    second base"): `OpenPosition` already inherits `IStoppablePosition`
    (`order_matching_policy.py`) as its one nominal ABC base, and `§2`
    forbids multiple inheritance — a second `abstractmethod`-bearing ABC base
    is not an option, so this stays structural instead.
    """

    @property
    def side(self) -> PositionSide: ...

    @property
    def leverage(self) -> float: ...

    @property
    def liquidation_price(self) -> float | None: ...


class MarginRiskPolicy:
    """
    @brief Domain policy for leverage, mark-to-market valuation, and PnL realization.
    """

    def get_leverage(
        self,
        side: PositionSide,
        long_leverage: float,
        short_leverage: float,
    ) -> float:
        """
        @brief Resolves configured leverage multiplier based on position direction.
        """
        return long_leverage if side is PositionSide.LONG else short_leverage

    def liquidation_price(
        self,
        side: PositionSide,
        leverage: float,
        entry_price: float,
    ) -> float | None:
        """
        @brief The price at which this position's margin is fully lost (`BOT-049`).

        @details Derived algebraically from this policy's own
        `calculate_realized_pnl`, not invented: liquidation is defined as the
        exit price at which `balance_release` hits exactly zero (fees aside —
        a threshold price, not a settlement). Solving
        `(exit_price - entry_price) * quantity - balance_before_entry = 0`
        for LONG, or the mirrored SHORT equation, with
        `balance_before_entry = entry_price * quantity / leverage` (this
        module's own margin formula), collapses `quantity` out entirely and
        gives `entry_price * (1 - 1/leverage)` for LONG and
        `entry_price * (1 + 1/leverage)` for SHORT.

        This is the **zero-maintenance-margin case** of the formula Binance's
        own Isolated Margin liquidation-price documentation publishes
        (`Liquidation Price = (WB + TMM + UPNL - cumB) / (Position × MMR_B -
        Side × Position)`, with `TMM = UPNL = 0` for isolated mode): setting
        the tiered `MMR_B`/`cumB` terms to zero reduces it to exactly this
        formula. Known, documented limitation, same shape as `BOT-049` §3's
        funding-fee exclusion: a real exchange's tiered maintenance-margin
        schedule triggers liquidation slightly *before* this price (its
        buffer against slippage during forced closure); this simulator does
        not model that buffer, so a leveraged backtest is not more
        conservative than reality on this axis.

        @return `None` for an unleveraged (1.0x) LONG — modeled as spot
        (`mark_to_market`'s own special case), which has no margin to lose
        and so cannot be liquidated. Every other case (leveraged LONG, any
        SHORT) always has one, since `calculate_realized_pnl` always routes
        them through the margin-based branch.
        """
        if side is PositionSide.LONG:
            if leverage == 1.0:
                return None
            return entry_price * (1.0 - 1.0 / leverage)
        return entry_price * (1.0 + 1.0 / leverage)

    def evaluate_liquidations[TPosition: ILiquidatablePosition](
        self, positions: Sequence[TPosition], high: float, low: float
    ) -> tuple[list[tuple[TPosition, float, ExitReason]], list[TPosition]]:
        """
        @brief Checks every open position's `liquidation_price` against bar high/low.
        @details Same shape as `OrderMatchingPolicy.evaluate_intrabar_stops` —
        a LONG liquidates when the bar's `low` reaches its (necessarily lower)
        liquidation price; a SHORT when the bar's `high` reaches its
        (necessarily higher) one. `PaperExchange.check_intrabar_stops` calls
        this **before** the stop-loss/take-profit check and removes triggered
        positions first, which is what makes liquidation win a same-bar race
        against SL/TP (`BOT-049` §2: a real exchange liquidates before a
        user's own stop order could fill).
        @return tuple of (triggered_positions_with_exit_price_and_reason, still_open_positions).
        """
        if not positions:
            return [], []

        triggered: list[tuple[TPosition, float, ExitReason]] = []
        still_open: list[TPosition] = []

        for pos in positions:
            liq_price = pos.liquidation_price
            if liq_price is None:
                still_open.append(pos)
                continue

            hit = (
                low <= liq_price if pos.side is PositionSide.LONG else high >= liq_price
            )
            if hit:
                triggered.append((pos, liq_price, ExitReason.LIQUIDATION))
            else:
                still_open.append(pos)

        return triggered, still_open

    def mark_to_market(
        self,
        side: PositionSide,
        leverage: float,
        quantity: float,
        entry_price: float,
        balance_before_entry: float,
        mark_price: float,
    ) -> float:
        """
        @brief Computes current mark-to-market account-value contribution of an open position.
        @details Unleveraged (1.0x) LONG preserves spot valuation (quantity * mark_price).
        Leveraged LONG and all SHORT positions use margin + unrealized PnL.
        """
        if side is PositionSide.LONG:
            if leverage == 1.0:
                return quantity * mark_price
            return balance_before_entry + (mark_price - entry_price) * quantity
        return balance_before_entry + (entry_price - mark_price) * quantity

    def calculate_realized_pnl(
        self,
        side: PositionSide,
        leverage: float,
        quantity: float,
        entry_price: float,
        exit_price: float,
        balance_before_entry: float,
        entry_fee: float,
        exit_fee: float,
    ) -> tuple[float, float, float]:
        """
        @brief Calculates realized PnL, PnL percentage, and balance release on position closure.
        @return tuple of (pnl, pnl_percent, balance_release).
        """
        notional = quantity * exit_price

        if side is PositionSide.LONG and leverage == 1.0:
            net_proceeds = notional - exit_fee
            pnl = net_proceeds - balance_before_entry
            balance_release = net_proceeds
        elif side is PositionSide.LONG:
            pnl = (exit_price - entry_price) * quantity - entry_fee - exit_fee
            balance_release = balance_before_entry + pnl
        else:
            pnl = (entry_price - exit_price) * quantity - entry_fee - exit_fee
            balance_release = balance_before_entry + pnl

        pnl_percent = (
            (pnl / balance_before_entry * 100.0) if balance_before_entry > 0 else 0.0
        )

        return pnl, pnl_percent, balance_release
