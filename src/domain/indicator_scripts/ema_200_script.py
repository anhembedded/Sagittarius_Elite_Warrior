from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)


class Ema200Script(BaseIndicatorScript):
    """EMA(200) — see ema_20_script.py for why this is its own script."""

    title = "EMA 200"
    overlay = True
    min_warmup_bars = 200
    default_enabled = True

    def setup(self) -> None:
        self.a = self.ema(200)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.a(candle.close_price), "EMA 200", color="#3498db")
