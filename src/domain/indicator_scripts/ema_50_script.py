from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)


class Ema50Script(BaseIndicatorScript):
    """EMA(50) — see ema_20_script.py for why this is its own script."""

    title = "EMA 50"
    overlay = True
    min_warmup_bars = 50  # tied to input_int's default below — see ema_20_script.py
    default_enabled = True

    def setup(self) -> None:
        period = self.input_int("period", 50, label="Period", minval=1)
        self.a = self.ema(period)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.a(candle.close_price), "EMA 50", color="#e67e22")
