from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicator_scripts.base_indicator_script import (
    BaseIndicatorScript,
)


class MacdFullScript(BaseIndicatorScript):
    """
    @brief MACD drawn as all three of its parts — MACD line, signal line, and
    histogram — on their own subplot row.

    @details Reference example for two things the single-value indicator path
    can't express:

    1. **A subplot** (`overlay = False`) — MACD oscillates around zero, so
       plotting it on the candles' price scale would be meaningless.
    2. **Fanning one reading out into several lines.** `MACD.update()` returns a
       `MACDValue`; here one handle call feeds three separate plotted lines
       (`.macd`/`.signal`/`.histogram`) — the reason a script is more
       expressive than a bare IIndicator. This is also the Dev Board's default
       MACD replacement (BOT-032 Phase 6 — no indicator is hardcoded in the
       engine anymore).

    The `if reading is not None` guard is needed because this reads *fields off*
    the reading; `plot()`'s own None-handling only covers passing a None value
    straight through.
    """

    title = "MACD (12/26/9)"
    overlay = False
    # 26 (slow EMA) + 9 (signal EMA of the MACD line) — tied to the input
    # defaults below (BOT-048), see ema_20_script.py for why this stays a
    # class attribute rather than computed per-instance for now.
    min_warmup_bars = 35

    def setup(self) -> None:
        fast = self.input_int("fast_period", 12, label="Fast Period", minval=1)
        slow = self.input_int("slow_period", 26, label="Slow Period", minval=1)
        signal = self.input_int("signal_period", 9, label="Signal Period", minval=1)
        self.m = self.macd(fast, slow, signal)

    def execute(self, candle: MarketData) -> None:
        reading = self.m(candle.close_price)
        if reading is None:
            return
        self.plot(reading.macd, "MACD", color="#2980b9")
        self.plot(reading.signal, "Signal", color="#e67e22")
        self.plot(reading.histogram, "Histogram", color="#848E9C")
