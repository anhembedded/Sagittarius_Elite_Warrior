from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)

# Colours are plain hex strings — the domain layer never imports a UI toolkit,
# so there is no QColor here (see the guard test in
# tests/unit/domain/test_indicator_script_conventions.py).
_BULL = "#0ECB81"
_BEAR = "#F6465D"
_NEUTRAL = "#848E9C"
_ACCENT = "#F3BA2F"


class DevIndicatorScript(BaseIndicatorScript):
    """
    @brief DEV reference script — exercises every part of the scripting API in
    one place, so a new script can be written by copying the technique it needs
    instead of reading the base class.

    @details
    This is a **showcase, not a trading study**: the combination of lines it
    draws is not meant to be useful, only to demonstrate each capability. Keep
    it registered so it stays compiled and tested; delete techniques from your
    own copy rather than adding to this one.

    Techniques demonstrated, in the order they appear below:

    | # | Technique | Pine equivalent |
    |---|---|---|
    | 1 | Declaring indicators (`ema`/`wma`/`rsi`/`macd`) | `ema(close, 12)` |
    | 2 | A hand-fed series for a derived value | assigning to a variable |
    | 3 | A constant level to compare against | `hline(70)` as an operand |
    | 4 | Reading OHLCV via the built-in price series | `close`, `high`, ... |
    | 5 | Looking back a bar (`[1]`) | `a[1]` |
    | 6 | Per-bar colour | `c = b > a ? lime : red` |
    | 7 | Skipping a bar | `na` |
    | 8 | Indicator crossing indicator | `crossover(a, b)` |
    | 9 | Indicator crossing price | `crossover(a, close)` |
    | 10 | Indicator crossing a constant | `crossover(rsi, 70)` |
    | 11 | Fanning a compound reading out | `macd`, `signal`, `hist` |
    | 12 | Markers with labels | `plotshape(..., text="Buy")` |

    `overlay = True`, so every plotted line shares the candles' price scale.
    For a study that needs its own row instead (RSI 0-100, MACD around zero),
    see `macd_full_script.py` — the only difference is `overlay = False`.
    """

    title = "DEV — scripting API showcase"
    overlay = True

    def setup(self) -> None:
        # --- 1. Declare indicators. These are the building blocks; the script
        # never implements the maths itself, it only composes them.
        self.fast = self.ema(12)
        self.slow = self.ema(26)
        self.weighted = self.wma(20)
        self.momentum = self.rsi(14)
        self.trend = self.macd()

        # --- 2. A Series for a value this script computes itself. Indicator
        # handles track their own history; a derived number has nowhere to live
        # unless you declare a Series for it here.
        self.spread = self.series()

        # --- 3. A constant, so a level can be crossed like any other line.
        self.overbought = self.level(70.0)

    def execute(self, candle: MarketData) -> None:
        # --- 4. Price. `candle` carries the raw bar, while self.close/high/...
        # are Series, so they can be compared and looked back through.
        close = candle.close_price
        session_range = candle.high_price - candle.low_price

        fast = self.fast(close)
        slow = self.slow(close)
        weighted = self.weighted(close)
        momentum = self.momentum(close)
        trend = self.trend(close)

        # --- 2b. Feed the derived Series every bar, including a None while its
        # inputs are still warming up — pushing nothing would silently shift
        # the bar alignment and make `[1]` mean the wrong bar.
        self.spread.push(fast - slow if fast is not None and slow is not None else None)

        # --- 5. Look back one bar. Guard for None: early bars have no history.
        widening = (
            self.spread[0] is not None
            and self.spread[1] is not None
            and abs(self.spread[0]) > abs(self.spread[1])
        )

        # --- 6. Per-bar colour: the same line changes colour as the trend flips.
        trend_color = _BULL if self.is_above(self.fast, self.slow) else _BEAR

        self.plot(fast, "EMA 12", color=trend_color)
        self.plot(slow, "EMA 26", color=trend_color)
        self.plot(weighted, "WMA 20", color=_NEUTRAL)

        # --- 7. Skipping a bar: passing None plots nothing for it, which is how
        # Pine's `na` is expressed. Here the band only exists while the gap
        # between the EMAs is growing.
        self.plot(
            close + session_range if widening else None,
            "Widening band",
            color=_ACCENT,
        )

        # --- 8. Indicator crossing indicator, and --- 12. markers. Nothing is
        # marked automatically; a marker exists only because it was asked for.
        if self.crossed_above(self.fast, self.slow):
            self.mark(fast, "Buy", color=_BULL, direction="up")
        elif self.crossed_below(self.fast, self.slow):
            self.mark(fast, "Sell", color=_BEAR, direction="down")

        # --- 9. Indicator crossing *price* — price is just another Series, so
        # this needs no special API.
        if self.crossed(self.weighted, self.close):
            self.mark(close, "WMA×Px", color=_NEUTRAL, direction="up")

        # --- 10. Crossing a constant level. RSI lives on a 0-100 scale that
        # would be meaningless drawn over price, so it is computed and used for
        # a marker without being plotted here.
        if self.crossed_above(self.momentum, self.overbought):
            self.mark(candle.high_price, "Overbought", color=_BEAR, direction="down")

        # --- 11. A compound reading. MACD.update() returns a MACDValue rather
        # than a float, so `self.trend[1]` is always None — read the fields
        # directly, and push one into a Series of your own if it needs history.
        if trend is not None and momentum is not None:
            self.mark(
                close if trend.histogram > 0 and momentum > 50 else None,
                "Strong",
                color=_ACCENT,
                direction="up",
            )
