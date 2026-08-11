from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)


class Rsi14Script(BaseIndicatorScript):
    """
    @brief RSI(14) — the Dev Board's default RSI, replacing the old hardcoded
    checkbox (BOT-032 Phase 6: no indicator is hardcoded in the engine).

    @details A fixed period rather than a configurable spinbox — scripts take
    no runtime parameters by design (see the BOT-032 task file's Phase 6
    notes). Wanting a different period means registering another script, the
    same pattern `ema_20_script.py`/`ema_50_script.py`/... use.
    """

    title = "RSI (14)"
    overlay = False
    min_warmup_bars = 14

    def setup(self) -> None:
        self.r = self.rsi(14)

    def execute(self, candle: MarketData) -> None:
        self.plot(self.r(candle.close_price), "RSI 14", color="#8e44ad")
