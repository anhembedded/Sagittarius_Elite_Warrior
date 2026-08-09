from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)


class Ema20Script(BaseIndicatorScript):
    """
    @brief EMA(20) — one of the Dev Board's default indicators (US-07: "no
    indicator hardcoded in the engine, default is EMA 200/100/50/20").

    @details A single, independently toggleable EMA rather than reusing
    `ema_ribbon_script.py` on purpose — that script draws all four EMAs as
    one unit with no way to enable just one of them. `default_enabled = True`
    is what makes it show up already checked the first time the app runs.
    """

    title = "EMA 20"
    overlay = True
    min_warmup_bars = 20
    default_enabled = True

    def setup(self) -> None:
        self.a = self.ema(20)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.a(candle.close_price), "EMA 20", color="#e74c3c")
