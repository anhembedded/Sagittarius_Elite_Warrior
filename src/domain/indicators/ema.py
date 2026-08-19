from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator


class EMA(IIndicator[float]):
    """
    @brief Exponential Moving Average, SMA-seeded (the convention used by
    virtually every published EMA reference table).
    @details The first `period` values are buffered and averaged (simple
    mean) to produce the seed; every value after that applies the standard
    EMA recurrence. Pure, stateful, zero I/O.
    """

    def __init__(self, period: int) -> None:
        if period <= 0:
            raise ValueError(f"EMA period must be positive, got {period}")
        self._period = period
        self._multiplier = 2 / (period + 1)
        self._seed_values: list[float] = []
        self._ema: float | None = None

    def update(self, value: float) -> float | None:
        if self._ema is None:
            self._seed_values.append(value)
            if len(self._seed_values) < self._period:
                return None
            self._ema = sum(self._seed_values) / self._period
            self._seed_values.clear()
            return self._ema

        self._ema = (value - self._ema) * self._multiplier + self._ema
        return self._ema

    def peek_provisional(self, value: float) -> float | None:
        if self._ema is None:
            # Still seeding — a provisional seed average would only be valid
            # once `period` values (including this tentative one) exist, and
            # buffering it would require mutating `_seed_values`. Warm-up
            # stays None for provisional too, matching `update()`.
            return None
        return (value - self._ema) * self._multiplier + self._ema
