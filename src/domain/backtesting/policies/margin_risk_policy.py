from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
)

logger = logging.getLogger("App.PaperExchange")


class MarginRiskPolicy:
    """
    @brief Domain policy for margin allocation, leverage, mark-to-market valuation, and PnL realization.
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

    def calculate_margin_and_notional(
        self,
        side: PositionSide,
        effective_price: float,
        current_equity: float,
        available_balance: float,
        sizing: PositionSizing,
        leverage: float,
        stop_loss_pct: float | None = None,
    ) -> tuple[float, float]:
        """
        @brief Calculates required margin and notional capital based on position sizing and leverage.
        @details
        - PERCENT_OF_EQUITY / FIXED_CASH: leverage scales margin into larger notional capital.
        - FIXED_CONTRACTS / RISK_PERCENT: leverage reduces required margin for the fixed contract count/risk.
        Clamps margin to available liquid balance while preserving the exact leverage ratio.
        @return tuple of (margin, notional_capital). Returns (0.0, 0.0) if invalid or insufficient.
        """
        if effective_price <= 0 or leverage <= 0:
            return 0.0, 0.0

        sizing_type = sizing.type
        sizing_val = sizing.value

        if sizing_type is PositionSizingType.PERCENT_OF_EQUITY:
            margin = current_equity * (sizing_val / 100.0)
            notional_capital = margin * leverage
        elif sizing_type is PositionSizingType.FIXED_CASH:
            margin = sizing_val
            notional_capital = margin * leverage
        elif sizing_type is PositionSizingType.FIXED_CONTRACTS:
            notional_capital = sizing_val * effective_price
            margin = notional_capital / leverage
        elif sizing_type is PositionSizingType.RISK_PERCENT:
            if stop_loss_pct is None or stop_loss_pct <= 0:
                logger.debug(
                    f"[paper-exchange] {side.value.upper()} rejected: RISK_PERCENT "
                    "sizing requires BrokerSimulationConfig.stop_loss_pct to be set"
                )
                return 0.0, 0.0
            stop_distance = effective_price * (stop_loss_pct / 100.0)
            if stop_distance <= 0:
                return 0.0, 0.0
            risk_amount = current_equity * (sizing_val / 100.0)
            notional_capital = risk_amount * (effective_price / stop_distance)
            margin = notional_capital / leverage
        else:
            margin = available_balance
            notional_capital = margin * leverage

        if margin > available_balance:
            scale = (available_balance / margin) if margin > 0 else 0.0
            margin = available_balance
            notional_capital *= scale

        if margin <= 0 or notional_capital <= 0:
            return 0.0, 0.0

        return margin, notional_capital

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
