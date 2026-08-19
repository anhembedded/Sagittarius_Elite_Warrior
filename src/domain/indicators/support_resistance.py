from collections import deque
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator


@dataclass(frozen=True)
class SupportResistanceValue:
    """
    @brief Immutable reading for Support & Resistance levels.
    @param resistance The highest price observed in the rolling lookback window.
    @param support The lowest price observed in the rolling lookback window.
    @param midline The equilibrium midpoint between resistance and support.
    """

    resistance: float
    support: float
    midline: float


class SupportResistance(IIndicator[SupportResistanceValue]):
    """
    @brief Support & Resistance Channel / Dynamic price boundaries.
    @details Tracks a rolling window of recent prices, calculating dynamic
    resistance (highest high), support (lowest low), and midline (equilibrium).
    Returns None until `period` values have been committed (warmup phase).
    """

    def __init__(self, period: int) -> None:
        if period <= 0:
            raise ValueError(f"SupportResistance period must be positive, got {period}")
        self._period = period
        self._values: deque[float] = deque(maxlen=period)

    @property
    def period(self) -> int:
        return self._period

    def update(self, value: float) -> SupportResistanceValue | None:
        self._values.append(value)
        if len(self._values) < self._period:
            return None

        resistance = max(self._values)
        support = min(self._values)
        midline = (resistance + support) / 2.0
        return SupportResistanceValue(
            resistance=resistance,
            support=support,
            midline=midline,
        )

    def peek_provisional(self, value: float) -> SupportResistanceValue | None:
        committed = list(self._values)
        window = (
            committed[1:] + [value]
            if len(committed) == self._period
            else [*committed, value]
        )
        if len(window) < self._period:
            return None

        resistance = max(window)
        support = min(window)
        midline = (resistance + support) / 2.0
        return SupportResistanceValue(
            resistance=resistance,
            support=support,
            midline=midline,
        )
