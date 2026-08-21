from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypeVar

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)


class IStoppablePosition(Protocol):
    """Protocol for positions evaluated in intrabar stop/target checks."""

    @property
    def side(self) -> PositionSide: ...

    @property
    def stop_loss_price(self) -> float | None: ...

    @property
    def take_profit_price(self) -> float | None: ...


TPosition = TypeVar("TPosition", bound=IStoppablePosition)


class OrderMatchingPolicy:
    """
    @brief Domain policy for order price execution, slippage, and intrabar stop/target matching.
    """

    def calculate_slippage_delta(self, slippage_ticks: int, tick_size: float) -> float:
        """
        @brief Calculates price friction delta from configured slippage ticks and tick size.
        """
        return slippage_ticks * tick_size

    def calculate_entry_effective_price(
        self, side: PositionSide, price: float, slippage_delta: float
    ) -> float:
        """
        @brief Calculates effective entry fill price considering slippage.
        @details A LONG entry buys (pays more); a SHORT entry sells (receives less).
        """
        if side is PositionSide.LONG:
            return price + slippage_delta
        return max(0.0, price - slippage_delta)

    def calculate_exit_effective_price(
        self, side: PositionSide, price: float, slippage_delta: float
    ) -> float:
        """
        @brief Calculates effective exit fill price considering slippage.
        @details A LONG exit sells (receives less); a SHORT exit/cover buys (pays more).
        """
        if side is PositionSide.LONG:
            return max(0.0, price - slippage_delta)
        return price + slippage_delta

    def calculate_stop_loss_price(
        self,
        side: PositionSide,
        effective_price: float,
        stop_loss_pct: float | None,
    ) -> float | None:
        """
        @brief Calculates absolute stop-loss price threshold from percentage offset.
        @details LONG stop sits BELOW entry; SHORT stop sits ABOVE entry.
        """
        if stop_loss_pct is None:
            return None
        stop_pct = stop_loss_pct / 100.0
        if side is PositionSide.LONG:
            return effective_price * (1.0 - stop_pct)
        return effective_price * (1.0 + stop_pct)

    def calculate_take_profit_price(
        self,
        side: PositionSide,
        effective_price: float,
        take_profit_pct: float | None,
    ) -> float | None:
        """
        @brief Calculates absolute take-profit price threshold from percentage offset.
        @details LONG target sits ABOVE entry; SHORT target sits BELOW entry.
        """
        if take_profit_pct is None:
            return None
        tp_pct = take_profit_pct / 100.0
        if side is PositionSide.LONG:
            return effective_price * (1.0 + tp_pct)
        return effective_price * (1.0 - tp_pct)

    def evaluate_intrabar_stops(
        self,
        positions: Sequence[TPosition],
        high: float,
        low: float,
    ) -> tuple[list[tuple[TPosition, float, ExitReason]], list[TPosition]]:
        """
        @brief Evaluates every open position against bar high/low boundaries.
        @details When a single bar touches both stop-loss and take-profit thresholds,
        stop-loss conservatively wins (BOT-041/BOT-050 convention).
        @return tuple of (triggered_positions_with_fill_price_and_reason, still_open_positions).
        """
        if not positions:
            return [], []

        triggered: list[tuple[TPosition, float, ExitReason]] = []
        still_open: list[TPosition] = []

        for pos in positions:
            sl_price = pos.stop_loss_price
            tp_price = pos.take_profit_price

            if pos.side is PositionSide.LONG:
                stop_hit = sl_price is not None and low <= sl_price
                target_hit = tp_price is not None and high >= tp_price
            else:
                stop_hit = sl_price is not None and high >= sl_price
                target_hit = tp_price is not None and low <= tp_price

            if stop_hit and sl_price is not None:
                triggered.append((pos, sl_price, ExitReason.STOP_LOSS))
            elif target_hit and tp_price is not None:
                triggered.append((pos, tp_price, ExitReason.TAKE_PROFIT))
            else:
                still_open.append(pos)

        return triggered, still_open
