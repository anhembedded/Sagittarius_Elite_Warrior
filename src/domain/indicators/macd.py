from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator

DEFAULT_MACD_FAST_PERIOD = 12
DEFAULT_MACD_SLOW_PERIOD = 26
DEFAULT_MACD_SIGNAL_PERIOD = 9


@dataclass(frozen=True)
class MACDValue:
    macd: float
    signal: float
    histogram: float


class MACD(IIndicator[MACDValue]):
    """
    @brief Moving Average Convergence/Divergence, composed of three EMAs
    (fast, slow, and a signal-line EMA of the MACD line) rather than
    reimplementing EMA's recurrence.
    @details The fast/slow EMAs are updated on every tick regardless of
    warm-up state — skipping them would stall their internal seed buffers.
    The signal EMA only starts receiving values once the MACD line itself
    exists, otherwise its own seed would be corrupted by placeholder input.
    """

    def __init__(
        self,
        fast_period: int = DEFAULT_MACD_FAST_PERIOD,
        slow_period: int = DEFAULT_MACD_SLOW_PERIOD,
        signal_period: int = DEFAULT_MACD_SIGNAL_PERIOD,
    ) -> None:
        if fast_period >= slow_period:
            raise ValueError(
                f"fast_period ({fast_period}) must be < slow_period ({slow_period})"
            )
        self._fast_ema = EMA(fast_period)
        self._slow_ema = EMA(slow_period)
        self._signal_ema = EMA(signal_period)

    def update(self, value: float) -> MACDValue | None:
        fast = self._fast_ema.update(value)
        slow = self._slow_ema.update(value)
        if fast is None or slow is None:
            return None

        macd_line = fast - slow
        signal = self._signal_ema.update(macd_line)
        if signal is None:
            return None

        return MACDValue(macd=macd_line, signal=signal, histogram=macd_line - signal)
