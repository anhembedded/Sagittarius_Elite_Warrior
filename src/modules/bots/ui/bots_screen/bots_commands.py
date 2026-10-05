"""The Bots mode's commands (`EPIC-033D`): New bot…, the selected bot's
lifecycle actions, Refresh fills and Fit levels.

Each is one `QAction` in the Bots menu, scoped to the mode, named and placed
as HLD §11.2.3 lists them: every lifecycle command but Delete bot is also on
its toolbar, and Save bot is the platform's Save (Ctrl+S on Windows).
Refresh fills and Fit levels are not in the catalogue yet; Fit levels was a
push button over the chart until `EPIC-033K` made the chart the centre. The
lifecycle commands act on the selected bot and follow its availability
(`bot_action_rules.py`). Stop… and Delete ask through the presenter's own
dialogs (`command_for`), because Stop asks how to stop; so neither carries
the Engine's confirmation. New bot… and Stop… ask for input, so they end
with "…"; Delete bot only confirms, so it takes none (`ui-presentation-rule.md`
§4), where the catalogue wrote "Delete bot…".

Qt-free, because `BotsModule.contribute()` imports it on a headless run
(`test_module_contribution_laziness.py`); the presenter's side is
`bots_command_binding.py`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)

from .bot_action_rules import BotAction

BOTS_MENU = ("&Bots",)
_CONTRIBUTOR = "bots"
_PREFIX = "bots.bots"

NEW_BOT = f"{_PREFIX}.new_bot"
REFRESH_FILLS = f"{_PREFIX}.refresh_fills"
FIT_LEVELS = f"{_PREFIX}.fit_levels"

#: Menu text per lifecycle action, in menu order; the toolbar ones are marked.
_LIFECYCLE: tuple[tuple[BotAction, str, bool], ...] = (
    (BotAction.SAVE, "&Save bot", True),
    (BotAction.START, "S&tart", True),
    (BotAction.PAUSE, "&Pause", True),
    (BotAction.RESUME, "&Resume", True),
    (BotAction.CONFIRM_RESUME, "&Confirm resume", True),
    (BotAction.STOP, "St&op…", True),
    (BotAction.DELETE, "&Delete bot", False),
)


def lifecycle_id(action: BotAction) -> str:
    return f"{_PREFIX}.{action.name.lower()}"


def bots_commands(route: str) -> tuple[CommandContribution, ...]:
    """The commands of the Bots mode at `route`, in menu order."""

    def command(
        command_id: str,
        text: str,
        *,
        on_toolbar: bool,
        needs_input: bool = False,
        standard_shortcut: str | None = None,
    ) -> CommandContribution:
        return CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=command_id,
            text=text,
            menu_path=BOTS_MENU,
            mode=route,
            on_toolbar=on_toolbar,
            needs_input=needs_input,
            standard_shortcut=standard_shortcut,
        )

    return (
        command(NEW_BOT, "&New bot…", on_toolbar=True, needs_input=True),
        *(
            command(
                lifecycle_id(action),
                text,
                on_toolbar=on_toolbar,
                needs_input=text.endswith("…"),
                standard_shortcut="Save" if action is BotAction.SAVE else None,
            )
            for action, text, on_toolbar in _LIFECYCLE
        ),
        command(REFRESH_FILLS, "Refresh &fills", on_toolbar=False),
        command(FIT_LEVELS, "Fit &levels", on_toolbar=False),
    )
