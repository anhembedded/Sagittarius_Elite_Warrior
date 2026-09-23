from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData

from .base_indicator_script import (
    BaseIndicatorScript,
)


class Ema200Script(BaseIndicatorScript):
    """EMA(200) — see ema_20_script.py for why this is its own script."""

    title = "EMA 200"
    overlay = True
    min_warmup_bars = (
        200  # class-level fallback; setup() overrides per-instance (BOT-063)
    )
    default_enabled = True

    def setup(self) -> None:
        period = self.input_int("period", 200, label="Period", minval=1)
        self.min_warmup_bars = period
        self.a = self.ema(period)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.a(candle.close_price), "EMA 200", color="#3498db")
