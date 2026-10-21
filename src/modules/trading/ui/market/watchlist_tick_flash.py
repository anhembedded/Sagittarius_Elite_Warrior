"""`EPIC-043D` — the Watchlist's price follows the person's tick-flash choice."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.watchlist_table_model import (
    WatchlistTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.tick_flash_preference import (
    TickFlashPreference,
)


def follow_tick_flash(
    model: WatchlistTableModel, preference: TickFlashPreference | None
) -> None:
    """Lets `model` flash its prices as `preference` says, now and after each change; the
    subscription ends with the model. `None` (no preference in this container) keeps it off."""
    if preference is None:
        return
    model.set_tick_flash(preference.enabled)
    stop = preference.subscribe(model.set_tick_flash)
    model.destroyed.connect(lambda *_: stop())
