from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)


class MacdFullScript(BaseIndicatorScript):
    """
    @brief MACD drawn as all three of its parts — MACD line, signal line, and
    histogram — on their own subplot row.

    @details Reference example for two things the single-value indicator path
    can't express:

    1. **A subplot** (`overlay = False`) — MACD oscillates around zero, so
       plotting it on the candles' price scale would be meaningless.
    2. **Fanning one reading out into several lines.** `MACD.update()` returns a
       `MACDValue`, and the Dev Board's built-in MACD checkbox keeps only
       `.macd`, discarding `.signal`/`.histogram`. Here one handle call feeds
       three separate plotted lines — the reason a script is more expressive
       than a bare IIndicator.

    The `if reading is not None` guard is needed because this reads *fields off*
    the reading; `plot()`'s own None-handling only covers passing a None value
    straight through.
    """

    title = "MACD (12/26/9) — full"
    overlay = False

    def setup(self) -> None:
        self.m = self.macd()

    def execute(self, candle: MarketData) -> None:
        reading = self.m(candle.close_price)
        if reading is None:
            return
        self.plot(reading.macd, "MACD", color="#2980b9")
        self.plot(reading.signal, "Signal", color="#e67e22")
        self.plot(reading.histogram, "Histogram", color="#848E9C")
