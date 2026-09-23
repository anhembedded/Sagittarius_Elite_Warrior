from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData

from .base_indicator_script import (
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
    #: Class-level fallback for a script never instantiated with real
    #: params (e.g. `IndicatorScriptListModel.set_available()`'s throwaway
    #: `cls()`-free reads). `setup()` below overrides this per-instance
    #: with the actual chosen period (`BOT-063`).
    min_warmup_bars = 20
    default_enabled = True

    def setup(self) -> None:
        period = self.input_int("period", 20, label="Period", minval=1)
        self.min_warmup_bars = period
        self.a = self.ema(period)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.a(candle.close_price), "EMA 20", color="#e74c3c")
