from collections import deque

from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator


class WMA(IIndicator[float]):
    """
    @brief Weighted Moving Average — the last `period` values weighted 1..n,
    so the newest bar counts most.

    @details Needed as its own primitive because HMA (Hull) is defined purely
    in terms of WMA: `wma(2*wma(src, n/2) - wma(src, n), sqrt(n))`. Composing
    it from EMA would give a different curve, not the same indicator.

    Returns None until `period` values have been seen, matching every other
    IIndicator's warm-up contract.
    """

    def __init__(self, period: int) -> None:
        if period <= 0:
            raise ValueError(f"WMA period must be positive, got {period}")
        self._period = period
        self._values: deque[float] = deque(maxlen=period)
        #: 1..period, so the most recent value carries weight `period`.
        self._weights = list(range(1, period + 1))
        self._weight_total = sum(self._weights)

    def update(self, value: float) -> float | None:
        self._values.append(value)
        if len(self._values) < self._period:
            return None

        weighted = sum(v * w for v, w in zip(self._values, self._weights, strict=True))
        return weighted / self._weight_total
