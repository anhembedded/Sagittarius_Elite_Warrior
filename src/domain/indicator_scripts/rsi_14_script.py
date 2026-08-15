from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)


class Rsi14Script(BaseIndicatorScript):
    """
    @brief RSI(14) — the Dev Board's default RSI, replacing the old hardcoded
    checkbox (BOT-032 Phase 6: no indicator is hardcoded in the engine).

    @details Period is now an input (BOT-048 — BOT-032 Phase 6's "no runtime
    parameters" note predates BOT-044's input_*() mechanism), default 14 so
    nothing about today's behavior changes.
    """

    title = "RSI (14)"
    overlay = False
    min_warmup_bars = 14  # tied to input_int's default below — see ema_20_script.py

    def setup(self) -> None:
        period = self.input_int("period", 14, label="Period", minval=2)
        self.r = self.rsi(period)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.r(candle.close_price), "RSI 14", color="#8e44ad")
