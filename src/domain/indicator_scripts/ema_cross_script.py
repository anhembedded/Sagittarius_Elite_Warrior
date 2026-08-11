from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)

_BULL = "#0ECB81"
_BEAR = "#F6465D"


class EmaCrossScript(BaseIndicatorScript):
    """
    @brief Fast/slow EMA pair that recolours as the trend flips.

    @details Reference for the crossing user story, and the closest equivalent
    of this Pine idiom:

        c = b > a ? color.lime : color.red
        plot(a, color=c)

    Two things worth copying from here:

    1. **`self.is_above(...)`** replaces the hand-written `b > a` comparison.
       Same meaning, but None-safe while either EMA is still warming up.
    2. **Per-bar colour** — the same line name is plotted with a different
       colour depending on the trend, exactly like Pine's ternary.

    Buy/Sell markers on a crossing bar are a trading *decision*, not an
    indicator reading — that's `EmaCrossoverStrategy`
    (`domain/strategies/ema_crossover_strategy.py`), not this script.
    """

    title = "EMA Cross 12/26"
    overlay = True
    min_warmup_bars = 26  # EMA 26 is the slower of the pair

    def setup(self) -> None:
        self.fast = self.ema(12)
        self.slow = self.ema(26)

    def execute(self, candle: MarketData) -> None:
        close = candle.close_price
        fast = self.fast(close)
        slow = self.slow(close)

        trend_color = _BULL if self.is_above(self.fast, self.slow) else _BEAR
        self.plot(fast, "EMA 12", color=trend_color)
        self.plot(slow, "EMA 26", color=trend_color)
