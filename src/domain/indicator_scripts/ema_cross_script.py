from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)

_BULL = "#0ECB81"
_BEAR = "#F6465D"


class EmaCrossScript(BaseIndicatorScript):
    """
    @brief Fast/slow EMA pair that recolours as the trend flips and tags each
    crossing bar with a Buy/Sell label.

    @details Reference for the crossing user story, and the closest equivalent
    of this Pine idiom:

        c = b > a ? color.lime : color.red
        crossup = b > a and b[1] < a[1]
        plotshape(crossup ? a : na, style=shape.labelup, text="Buy", ...)

    Three things worth copying from here:

    1. **`self.crossed_above(...)`** replaces the hand-written
       `b > a and b[1] < a[1]`. Same meaning, but it also returns False
       instead of raising while either EMA is still warming up.
    2. **Per-bar colour** — the same line name is plotted with a different
       colour depending on the trend, exactly like Pine's ternary.
    3. **`na`** — `self.mark(value if crossed else None, ...)` mirrors
       `crossup ? a : na`; a None is simply skipped for that bar.
    """

    title = "EMA Cross 12/26"
    overlay = True

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

        if self.crossed_above(self.fast, self.slow):
            self.mark(fast, "Buy", color=_BULL, direction="up")
        elif self.crossed_below(self.fast, self.slow):
            self.mark(fast, "Sell", color=_BEAR, direction="down")
