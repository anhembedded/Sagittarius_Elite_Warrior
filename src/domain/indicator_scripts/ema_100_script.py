from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)


class Ema100Script(BaseIndicatorScript):
    """EMA(100) — see ema_20_script.py for why this is its own script."""

    title = "EMA 100"
    overlay = True
    min_warmup_bars = 100
    default_enabled = True

    def setup(self) -> None:
        self.a = self.ema(100)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.a(candle.close_price), "EMA 100", color="#00bcd4")
