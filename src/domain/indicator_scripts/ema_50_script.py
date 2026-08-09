from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)


class Ema50Script(BaseIndicatorScript):
    """EMA(50) — see ema_20_script.py for why this is its own script."""

    title = "EMA 50"
    overlay = True
    min_warmup_bars = 50
    default_enabled = True

    def setup(self) -> None:
        self.a = self.ema(50)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.a(candle.close_price), "EMA 50", color="#e67e22")
