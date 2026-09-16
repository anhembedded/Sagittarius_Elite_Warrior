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

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


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
