from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import TypeVar

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


class IStoppablePosition(ABC):
    """Contract for positions evaluated in intrabar stop/target checks.

    `ABC`, not `Protocol` (`architecture-rule.md` §2.1 default): the sole
    implementer, `OpenPosition` (`open_position.py`), is a plain
    `@dataclass` with no competing base class and no `QObject`/third-party
    constraint — none of the 3 reasons that justify `Protocol` apply, so
    nominal inheritance costs nothing here.
    """

    @property
    @abstractmethod
    def side(self) -> PositionSide: ...

    @property
    @abstractmethod
    def stop_loss_price(self) -> float | None: ...

    @property
    @abstractmethod
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

    def _touch_flags(
        self, pos: IStoppablePosition, high: float, low: float
    ) -> tuple[bool, bool]:
        """
        @brief (stop_hit, target_hit) for one position against one bar's
        high/low boundaries.
        @details Single source of truth for the LONG/SHORT crossing rule,
        shared by `evaluate_intrabar_stops()`'s own bar check and
        `_resolve_ambiguous_stop()`'s finer sub-candle walk (BOT-105B) —
        both ask exactly the same question, just at different resolutions.
        """
        sl_price = pos.stop_loss_price
        tp_price = pos.take_profit_price
        if pos.side is PositionSide.LONG:
            stop_hit = sl_price is not None and low <= sl_price
            target_hit = tp_price is not None and high >= tp_price
        else:
            stop_hit = sl_price is not None and high >= sl_price
            target_hit = tp_price is not None and low <= tp_price
        return stop_hit, target_hit

    def _resolve_ambiguous_stop(
        self,
        pos: IStoppablePosition,
        magnifier_candles: Sequence[tuple[float, float]] | None,
    ) -> ExitReason:
        """
        @brief BOT-105B — decides SL-vs-TP order for a bar that touched
        both, using finer sub-candles when available.
        @details `magnifier_candles` is an ordered, chronological sequence
        of (high, low) pairs spanning the enclosing bar (from a finer
        resolution than the bar itself, e.g. 1m sub-candles of a 15m bar).
        The first sub-candle that resolves either threshold decides the
        real order — a plain pair rather than a richer candle type because
        this is the only data the tie-break needs (Interface Segregation);
        the caller owns turning real klines into these pairs. Falls back to
        the BOT-041/BOT-050 pessimistic STOP_LOSS default when no magnifier
        data was supplied, or when even the finest sub-candle still
        straddles both thresholds (the ambiguity is real at that
        resolution too, not a lookup failure).
        """
        if not magnifier_candles:
            return ExitReason.STOP_LOSS

        for sub_high, sub_low in magnifier_candles:
            stop_hit, target_hit = self._touch_flags(pos, sub_high, sub_low)
            if stop_hit:
                return ExitReason.STOP_LOSS
            if target_hit:
                return ExitReason.TAKE_PROFIT

        return ExitReason.STOP_LOSS

    def evaluate_intrabar_stops(
        self,
        positions: Sequence[TPosition],
        high: float,
        low: float,
        magnifier_lookup: Callable[[], Sequence[tuple[float, float]]] | None = None,
    ) -> tuple[list[tuple[TPosition, float, ExitReason]], list[TPosition]]:
        """
        @brief Evaluates every open position against bar high/low boundaries.
        @details When a single bar touches both stop-loss and take-profit
        thresholds, `magnifier_lookup` (BOT-105B) decides the tie: called
        at most once per bar, lazily — only the first position actually
        found ambiguous triggers it, and every other position in the same
        bar reuses that one result — so a normal bar with no conflict, and
        a run with no `magnifier_lookup` at all, never pay for it. Without
        one (the default), stop-loss conservatively wins
        (BOT-041/BOT-050 convention) rather than guessing optimistically.
        @return tuple of (triggered_positions_with_fill_price_and_reason, still_open_positions).
        """
        if not positions:
            return [], []

        triggered: list[tuple[TPosition, float, ExitReason]] = []
        still_open: list[TPosition] = []
        magnifier_candles: Sequence[tuple[float, float]] | None = None
        magnifier_fetched = False

        for pos in positions:
            sl_price = pos.stop_loss_price
            tp_price = pos.take_profit_price
            stop_hit, target_hit = self._touch_flags(pos, high, low)

            if (
                stop_hit
                and target_hit
                and sl_price is not None
                and tp_price is not None
            ):
                if not magnifier_fetched:
                    magnifier_candles = (
                        magnifier_lookup() if magnifier_lookup is not None else None
                    )
                    magnifier_fetched = True
                reason = self._resolve_ambiguous_stop(pos, magnifier_candles)
                price = sl_price if reason is ExitReason.STOP_LOSS else tp_price
                triggered.append((pos, price, reason))
            elif stop_hit and sl_price is not None:
                triggered.append((pos, sl_price, ExitReason.STOP_LOSS))
            elif target_hit and tp_price is not None:
                triggered.append((pos, tp_price, ExitReason.TAKE_PROFIT))
            else:
                still_open.append(pos)

        return triggered, still_open
