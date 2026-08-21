from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator

DEFAULT_RSI_PERIOD = 14


class RSI(IIndicator[float]):
    """
    @brief Relative Strength Index using Wilder's smoothing.
    @details Composes two EMA instances configured with Wilder's smoothing factor
    (alpha = 1 / period), seeded by simple mean over the first `period` deltas,
    then applying recurrence for every subsequent value.
    Pure, stateful, zero I/O.
    """

    def __init__(self, period: int = DEFAULT_RSI_PERIOD) -> None:
        if period <= 0:
            raise ValueError(f"RSI period must be positive, got {period}")
        self._period = period
        self._previous_close: float | None = None
        self._gain_smoother = EMA(period=period, alpha=1.0 / period)
        self._loss_smoother = EMA(period=period, alpha=1.0 / period)

    def update(self, value: float) -> float | None:
        if self._previous_close is None:
            self._previous_close = value
            return None

        change = value - self._previous_close
        self._previous_close = value
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        avg_gain = self._gain_smoother.update(gain)
        avg_loss = self._loss_smoother.update(loss)

        if avg_gain is None or avg_loss is None:
            return None

        return self._compute_rsi_from(avg_gain, avg_loss)

    def peek_provisional(self, value: float) -> float | None:
        if self._previous_close is None:
            return None

        change = value - self._previous_close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        prov_avg_gain = self._gain_smoother.peek_provisional(gain)
        prov_avg_loss = self._loss_smoother.peek_provisional(loss)

        if prov_avg_gain is None or prov_avg_loss is None:
            return None

        return self._compute_rsi_from(prov_avg_gain, prov_avg_loss)

    @staticmethod
    def _compute_rsi_from(avg_gain: float, avg_loss: float) -> float:
        if avg_loss == 0.0:
            return 100.0 if avg_gain > 0.0 else 50.0
        relative_strength = avg_gain / avg_loss
        return 100.0 - 100.0 / (1.0 + relative_strength)
