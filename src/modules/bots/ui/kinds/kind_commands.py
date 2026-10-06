"""Each bot kind's own commands (`EPIC-033K` stage 2, HLD §11.2.3: "the
selected kind's commands … the kind's toolbar").

SPEC-014: "each bot type has its own toolbar". A kind declares its commands
here, by `kind_id`; the Bots mode puts every one in the Bots menu, and the
kind's editor (`BotKindPanel.kind_actions`) holds the toolbar that shows
them while a bot of that kind is selected. In the menu each command is
enabled only while the selected kind's toolbar action is (`KindCommands`),
so with no bot, or a bot of another kind, it is disabled, never hidden
(`ui-presentation-rule.md` §2).

Qt-free, because `bots_commands.py` contributes these on a headless run
(`test_module_contribution_laziness.py`).

Plausible extensions, each a local change: a second kind's commands (one
entry in `KIND_COMMANDS`, its editor's `kind_actions`); a checkable kind
command (one field here, as `CommandContribution.checkable`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
)


@dataclass(frozen=True, slots=True)
class KindCommand:
    """One command of one kind."""

    command_id: str
    #: Menu text: sentence case, one `&` access key, unique in the Bots menu.
    text: str


SUGGEST_FROM_ATR = "bots.bots.grid.suggest_from_atr"
SUGGEST_FROM_BOLLINGER = "bots.bots.grid.suggest_from_bollinger"

#: Each kind's commands, in menu order, by `kind_id`.
KIND_COMMANDS: Mapping[str, tuple[KindCommand, ...]] = {
    GRID_KIND_ID: (
        KindCommand(SUGGEST_FROM_ATR, "Suggest from &ATR"),
        KindCommand(SUGGEST_FROM_BOLLINGER, "Suggest from Bollin&ger"),
    ),
}


def all_kind_commands() -> tuple[KindCommand, ...]:
    """Every kind's commands, kind after kind."""
    return tuple(command for commands in KIND_COMMANDS.values() for command in commands)
