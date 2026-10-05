"""The Bots mode's commands (`EPIC-033D`): New bot…, the selected bot's
lifecycle actions and Refresh fills.

Each is one `QAction` in the Bots menu ("B&ots": Backtest holds B), scoped to
the mode; New bot…, Start, Pause and Stop… are also on its toolbar. The
lifecycle commands act on the selected bot and follow its availability
(`bot_action_rules.py`). Stop… and Delete ask through the presenter's own
dialogs (`command_for`), because Stop asks how to stop; so neither carries
the Engine's confirmation. New bot… and Stop… ask for input, so they end
with "…".

Qt-free, because `BotsModule.contribute()` imports it on a headless run
(`test_module_contribution_laziness.py`); the presenter's side is
`bots_command_binding.py`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)

from .bot_action_rules import BotAction

BOTS_MENU = ("B&ots",)
_CONTRIBUTOR = "bots"
_PREFIX = "bots.bots"

NEW_BOT = f"{_PREFIX}.new_bot"
REFRESH_FILLS = f"{_PREFIX}.refresh_fills"

#: Menu text per lifecycle action, in menu order; the toolbar ones are marked.
_LIFECYCLE: tuple[tuple[BotAction, str, bool], ...] = (
    (BotAction.START, "&Start", True),
    (BotAction.PAUSE, "&Pause", True),
    (BotAction.RESUME, "&Resume", False),
    (BotAction.CONFIRM_RESUME, "&Confirm resume", False),
    (BotAction.STOP, "S&top…", True),
    (BotAction.SAVE, "Sa&ve", False),
    (BotAction.DELETE, "&Delete", False),
)


def lifecycle_id(action: BotAction) -> str:
    return f"{_PREFIX}.{action.name.lower()}"


def bots_commands(route: str) -> tuple[CommandContribution, ...]:
    """The commands of the Bots mode at `route`, in menu order."""

    def command(
        command_id: str, text: str, *, on_toolbar: bool, needs_input: bool = False
    ) -> CommandContribution:
        return CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=command_id,
            text=text,
            menu_path=BOTS_MENU,
            mode=route,
            on_toolbar=on_toolbar,
            needs_input=needs_input,
        )

    return (
        command(NEW_BOT, "&New bot…", on_toolbar=True, needs_input=True),
        *(
            command(
                lifecycle_id(action),
                text,
                on_toolbar=on_toolbar,
                needs_input=text.endswith("…"),
            )
            for action, text, on_toolbar in _LIFECYCLE
        ),
        command(REFRESH_FILLS, "Refresh &fills", on_toolbar=False),
    )
