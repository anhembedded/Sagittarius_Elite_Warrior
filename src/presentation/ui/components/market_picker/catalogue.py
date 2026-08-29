"""Every market this app knows, named in Vietnamese.

Pure data: no Qt import, so it is testable without a `QApplication` — same
reasoning `timeframe_picker/catalogue.py` documents for itself. Unlike that
catalogue, this one needs no grouping: three markets fit on screen as a
flat list, and `SelectList` (the shared "choose 1" component) already
renders a flat list — nothing here does that job over again.
"""

from __future__ import annotations

from .....domain.value_objects.market_type import MarketType

#: Display order and Vietnamese label per market.
_LABELS: dict[MarketType, str] = {
    MarketType.SPOT: "Spot",
    MarketType.FUTURES_USD_M: "Futures (USD-M)",
    MarketType.FUTURES_COIN_M: "Futures (COIN-M)",
}

#: `SelectListVM.rows()` reads this exact shape (`id`/`label`) — the same
#: contract `StrategyPickerDialog`'s `get_options` already returns.
MARKET_OPTIONS: tuple[dict[str, str], ...] = tuple(
    {"id": market.value, "label": label} for market, label in _LABELS.items()
)
