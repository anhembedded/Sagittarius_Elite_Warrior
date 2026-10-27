"""`EPIC-047H` — the types of `market_data` that cross the remote link, each under its wire name.

One root: a window of closed candles (`CandleWindow`), the answer to the bridge's `candles` call.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.wire_root import WireRoot
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.closed_candle_window import (
    CANDLE_WINDOW_ROOT,
    CandleWindow,
)

MARKET_DATA_WIRE_ROOTS: tuple[WireRoot, ...] = (
    WireRoot(CANDLE_WINDOW_ROOT, CandleWindow),
)
