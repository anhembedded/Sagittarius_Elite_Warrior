"""Every market this app knows, named in Vietnamese.

Pure data: no Qt import, so it is testable without a `QApplication` — same
reasoning `timeframe_picker/catalogue.py` documents for itself. Unlike that
catalogue, this one needs no grouping: three markets fit on screen as a
flat list, and `kit.PickerOverlay` (the shared "choose 1" component) already
renders a flat list — nothing here does that job over again.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

#: Display order and Vietnamese label per market.
_LABELS = EnumLabels(
    MarketType,
    {
        MarketType.SPOT: "Spot",
        MarketType.FUTURES_USD_M: "Futures (USD-M)",
        MarketType.FUTURES_COIN_M: "Futures (COIN-M)",
    },
)

#: `overlay.py` maps this shape (`id`/`label`) into `kit.PickerItem`. It stayed
#: a dict through `EPIC-025` PR 4.3e rather than becoming `PickerItem` here,
#: because that would put a Qt import in a file whose docstring above promises
#: none — `PickerItem` lives in a `kit` module that imports `PySide6`.
MARKET_OPTIONS: tuple[dict[str, str], ...] = tuple(
    {"id": market.value, "label": label} for market, label in _LABELS.items()
)
