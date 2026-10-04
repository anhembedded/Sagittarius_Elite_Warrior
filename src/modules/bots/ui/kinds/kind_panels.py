"""`EPIC-029F` — each kind's parameter editor, by `kind_id`.

The one place the UI names a kind: a new kind adds its editor here and its
`IBotKind` to the catalog, and the screen does not change.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)

_PANELS: Mapping[str, Callable[[], BotKindPanel]] = {GRID_KIND_ID: GridPanel}

#: What the New Bot dialog lists, by `kind_id`.
KIND_TITLES: Mapping[str, str] = {GRID_KIND_ID: "Spot Grid"}

#: Which definition key holds the capital the bot may use, by `kind_id`; the
#: detail panel shows it beside every kind's profit.
KIND_CAPITAL_KEYS: Mapping[str, str] = {GRID_KIND_ID: "capital_quote"}


def panel_for(kind_id: str) -> BotKindPanel:
    """@raise UnknownBotKindError No editor is registered for `kind_id`."""
    try:
        return _PANELS[kind_id]()
    except KeyError:
        raise UnknownBotKindError(kind_id) from None
