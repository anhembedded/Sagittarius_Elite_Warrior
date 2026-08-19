from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator

DEFAULT_RSI_PERIOD = 14


class RSI(IIndicator[float]):
    """
    @brief Relative Strength Index using Wilder's smoothing.
    @details Seeds average gain/loss with a simple mean over the first
    `period` deltas, then applies Wilder's recurrence for every value after.
    Pure, stateful, zero I/O.
    """

    def __init__(self, period: int = DEFAULT_RSI_PERIOD) -> None:
        if period <= 0:
            raise ValueError(f"RSI period must be positive, got {period}")
        self._period = period
        self._previous_close: float | None = None
        self._gain_sum = 0.0
        self._loss_sum = 0.0
        self._deltas_seen = 0
        self._avg_gain: float | None = None
        self._avg_loss: float | None = None

    def update(self, value: float) -> float | None:
        if self._previous_close is None:
            self._previous_close = value
            return None

        change = value - self._previous_close
        self._previous_close = value
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        if self._avg_gain is None or self._avg_loss is None:
            return self._seed(gain, loss)

        self._avg_gain = (self._avg_gain * (self._period - 1) + gain) / self._period
        self._avg_loss = (self._avg_loss * (self._period - 1) + loss) / self._period
        return self._compute_rsi()

    def peek_provisional(self, value: float) -> float | None:
        if (
            self._previous_close is None
            or self._avg_gain is None
            or self._avg_loss is None
        ):
            # No committed previous close yet, or still accumulating the
            # seed sums — a provisional reading here would need mutating
            # `_gain_sum`/`_loss_sum`/`_deltas_seen` to mean anything, which
            # would corrupt the real seed. Stays None, matching `update()`.
            return None

        change = value - self._previous_close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        provisional_avg_gain = (
            self._avg_gain * (self._period - 1) + gain
        ) / self._period
        provisional_avg_loss = (
            self._avg_loss * (self._period - 1) + loss
        ) / self._period
        return self._compute_rsi_from(provisional_avg_gain, provisional_avg_loss)

    def _seed(self, gain: float, loss: float) -> float | None:
        self._gain_sum += gain
        self._loss_sum += loss
        self._deltas_seen += 1
        if self._deltas_seen < self._period:
            return None

        self._avg_gain = self._gain_sum / self._period
        self._avg_loss = self._loss_sum / self._period
        return self._compute_rsi()

    def _compute_rsi(self) -> float:
        return self._compute_rsi_from(self._avg_gain, self._avg_loss)

    @staticmethod
    def _compute_rsi_from(avg_gain: float, avg_loss: float) -> float:
        if avg_loss == 0.0:
            return 100.0 if avg_gain > 0.0 else 50.0
        relative_strength = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + relative_strength)
