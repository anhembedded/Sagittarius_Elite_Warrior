"""`EPIC-029F` — what a kind's parameter editor offers the Bots screen.

One editor per kind, found by `kind_id` (`kind_panels.py`), so the screen's
shell never names Grid: it hands the editor a definition's parameters and the
planner's market numbers, and hears each edit. Judging the parameters is the
kind's own `IBotKind.validate`, called by the screen, never by the editor.

A `QWidget` base rather than an `ABC`: Shiboken's metaclass conflicts with
`ABCMeta`, so the contract is held the way `BaseFeed` holds its own: each
method raises until a subclass implements it.
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict


class BotKindPanel(QWidget):
    """@brief A kind's parameter editor."""

    #: Emitted with the full parameter mapping after every user edit.
    config_changed = Signal(object)

    def set_config(self, config: Mapping[str, str]) -> None:
        """Shows `config` without emitting `config_changed`."""
        raise NotImplementedError(f"{type(self).__name__}.set_config")

    def config(self) -> dict[str, str]:
        """The parameters as the fields now read, as strings."""
        raise NotImplementedError(f"{type(self).__name__}.config")

    def set_planner_market(self, market: PlannerMarket | None) -> None:
        """The planner's numbers; suggestions are offered only when present."""
        raise NotImplementedError(f"{type(self).__name__}.set_planner_market")

    def set_editable(self, editable: bool) -> None:
        """Read-only while the bot runs, or while an action is in flight."""
        raise NotImplementedError(f"{type(self).__name__}.set_editable")

    def kind_actions(self) -> Mapping[str, QAction]:
        """The actions of the kind's own toolbar, by the command id
        `kind_commands.py` declares for each; the Bots menu's command of the
        same id triggers it and is enabled while it is. A kind with no
        commands of its own keeps this default."""
        return {}

    def show_verdicts(self, verdicts: tuple[Verdict, ...]) -> None:
        """Marks each field a verdict is about with its message and number
        (`EPIC-034F`). A kind that marks none keeps this default."""

    def focus_field(self, code: str) -> bool:
        """Brings the field the verdict `code` is about forward for editing;
        `False` when it is about no field of this editor."""
        return False
