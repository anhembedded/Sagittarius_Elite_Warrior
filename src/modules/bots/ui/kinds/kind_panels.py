"""`EPIC-029F` — each kind's parameter editor, by `kind_id`.

The one place the UI names a kind: a new kind adds its editor here and its `IBotKind` to the
catalog, and the screen does not change. The backtest is no longer registered here
(`EPIC-040F`): the kind-neutral workbench hosts every kind, so a new kind writes no page. The recipes:
· a kind's backtest — its `IKindBacktester`, returned by `IBotKind.backtester()`, answering a
  `BacktestOutcome` (`bots/contracts/i_kind_backtester.py`); the workbench draws it, and
  `IBotKind.supported_profiles()` says which markets it replays;
· a kind's parameter editor — one `BotKindPanel` entry in `_PANELS`;
· a kind with no backtest — `IBotKind.backtester()` answers `None`, and the Backtest tab is off with
  the reason in words (`bots_screen/backtest_workbenches.py`).
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

#: What a kind is called, by `kind_id`.
_KIND_NAMES: Mapping[str, str] = {GRID_KIND_ID: "Grid"}

#: Which definition key holds the capital the bot may use, by `kind_id`; the
#: detail panel shows it beside every kind's profit.
KIND_CAPITAL_KEYS: Mapping[str, str] = {GRID_KIND_ID: "capital_quote"}


def kind_title(kind_id: str) -> str:
    """The kind as the user reads it: "Grid", on Spot and on Futures alike. The venue says
    which market; a kind with no name is shown by its id (`BUG-208`)."""
    return _KIND_NAMES.get(kind_id, kind_id)


def panel_for(kind_id: str) -> BotKindPanel:
    """@raise UnknownBotKindError No editor is registered for `kind_id`."""
    try:
        return _PANELS[kind_id]()
    except KeyError:
        raise UnknownBotKindError(kind_id) from None
