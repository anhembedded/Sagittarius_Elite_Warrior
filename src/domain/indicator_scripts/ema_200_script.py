from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)


class Ema200Script(BaseIndicatorScript):
    """EMA(200) — see ema_20_script.py for why this is its own script."""

    title = "EMA 200"
    overlay = True
    min_warmup_bars = 200  # tied to input_int's default below — see ema_20_script.py
    default_enabled = True

    def setup(self) -> None:
        period = self.input_int("period", 200, label="Period", minval=1)
        self.a = self.ema(period)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.a(candle.close_price), "EMA 200", color="#3498db")
