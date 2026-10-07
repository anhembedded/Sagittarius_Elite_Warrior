"""The Bots mode's commands (`EPIC-033D`): New bot…, the selected bot's
lifecycle actions, each kind's own commands (`kind_commands.py`), Refresh
fills, Fit levels, and Arm strategy… / Disarm strategy for the Strategies
panel's selected venue (`EPIC-033K` stage 3; HLD §11.2: a strategy armed on a
venue is a row of the Bots mode until `EPIC-029L`).

Each is one `QAction` in the Bots menu, scoped to the mode, named and placed
as HLD §11.2.3 lists them: every lifecycle command but Delete bot is also on
its toolbar, and Save bot is the platform's Save (Ctrl+S on Windows).
Fit levels was a push button over the chart until `EPIC-033K` made the chart
the centre; it and Refresh fills joined the catalogue in `EPIC-033K` stage 4
(`test_bots_mode_catalogue.py` holds the menu and the toolbar to it). The
lifecycle commands act on the selected bot and follow its availability
(`bot_action_rules.py`). Stop… and Delete ask through the presenter's own
dialogs (`command_for`), because Stop asks how to stop; so neither carries
the Engine's confirmation. New bot… and Stop… ask for input, so they end
with "…"; Delete bot only confirms, so it takes none (`ui-presentation-rule.md`
§4).

Qt-free, because `BotsModule.contribute()` imports it on a headless run
(`test_module_contribution_laziness.py`); the presenter's side is
`bots_command_binding.py`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_commands import (
    all_kind_commands,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_stream_command import (
    live_stream_command,
)

from .bot_action_rules import BotAction

BOTS_MENU = ("&Bots",)
_CONTRIBUTOR = "bots"
_PREFIX = "bots.bots"
#: The prefix of the commands that follow the selected bot's chart.
COMMAND_PREFIX = _PREFIX

NEW_BOT = f"{_PREFIX}.new_bot"
REFRESH_FILLS = f"{_PREFIX}.refresh_fills"
FIT_LEVELS = f"{_PREFIX}.fit_levels"
ARM_STRATEGY = f"{_PREFIX}.arm_strategy"
DISARM_STRATEGY = f"{_PREFIX}.disarm_strategy"

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
        # On the kind's own toolbar, not the mode's (HLD §11.2.3).
        *(
            command(kind_command.command_id, kind_command.text, on_toolbar=False)
            for kind_command in all_kind_commands()
        ),
        command(REFRESH_FILLS, "Refresh &fills", on_toolbar=False),
        command(FIT_LEVELS, "Fit &levels", on_toolbar=False),
        live_stream_command(_CONTRIBUTOR, _PREFIX, route, BOTS_MENU, "Li&ve stream"),
        # The Strategies panel's selected venue: M and I are free in the menu.
        command(ARM_STRATEGY, "Ar&m strategy…", on_toolbar=False, needs_input=True),
        command(DISARM_STRATEGY, "D&isarm strategy", on_toolbar=False),
    )
