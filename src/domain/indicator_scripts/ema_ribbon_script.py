from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)


class EmaRibbonScript(BaseIndicatorScript):
    """
    @brief Four EMAs of increasing period drawn over the candles — the classic
    "ribbon" whose fanning/compression shows trend strength.

    @details Reference example for writing a script: declare handles in
    `setup()`, call them in `execute()`, hand each result to `plot()`. Nothing
    here computes an average itself — `self.ema()` wraps the existing, already
    tested `EMA` class.
    """

    title = "EMA Ribbon 20/50/100/200"
    overlay = True
    min_warmup_bars = 200  # EMA 200 is the slowest of the four

    def setup(self) -> None:
        self.a1 = self.ema(20)
        self.a2 = self.ema(50)
        self.a3 = self.ema(100)
        self.a4 = self.ema(200)

    def execute(self, candle: MarketData) -> None:
        close = candle.close_price
        self.plot(self.a1(close), "EMA 20", color="#e74c3c")
        self.plot(self.a2(close), "EMA 50", color="#e67e22")
        self.plot(self.a3(close), "EMA 100", color="#00bcd4")
        self.plot(self.a4(close), "EMA 200", color="#3498db")
