"""The selected kind's commands in the Bots menu, driving the kind's own
toolbar (`EPIC-033K` stage 2, HLD §11.2.3).

The toolbar is the kind's editor's (`BotKindPanel.kind_actions`), shown
while a bot of that kind is selected; a toolbar's buttons take no keyboard
focus, so the menu is how a keyboard reaches them (`ui-presentation-rule.md`
§2, §6). The menu's actions are the shell's, one per command
`kind_commands.py` declares, kept in step by the shared `ActionMirror` as the
Backtest chart's commands are: a menu command triggers the editor's action,
and the editor's action says whether it is enabled. With no bot selected, or
a bot whose kind lacks the command, the command is disabled.

Presenter-owned (`async-ui-action-rule.md` §2): built when the mode's commands
are bound, parented to the view model, and handed each new editor by
`follow_panel_of()`.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_commands import (
    all_kind_commands,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_mirror import ActionMirror


class KindCommands(ActionMirror):
    """@brief The Bots menu's kind commands, following the kind's toolbar."""

    def __init__(self, parent: QObject) -> None:
        # The editor's actions are keyed by the command ids themselves.
        super().__init__(
            {command.command_id: command.command_id for command in all_kind_commands()},
            parent,
        )

    @classmethod
    def follow_panel_of(cls, owner: QObject, panel: BotKindPanel | None) -> None:
        """Hands the editor just shown to the commands `owner` (the
        presenter's view model) holds; `None` means no bot is selected."""
        for commands in owner.findChildren(
            cls, options=Qt.FindChildOption.FindDirectChildrenOnly
        ):
            commands.follow(panel.kind_actions() if panel is not None else None)
