"""The Bots mode's commands (`EPIC-033D`): New bot…, the selected bot's
lifecycle actions, each kind's own commands (`kind_commands.py`), Refresh
fills, Fit levels, Retry venue account (`EPIC-034D`), Refresh exchange check
(`BOT-174`), Fix next item (`EPIC-034H`), Export plan… (`BOT-176`), and Arm strategy… / Disarm strategy… (`EPIC-033K` stage 3; `BOT-219`:
each asks which venue, since there is no Strategies panel to select one).

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
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    chart_commands,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_stream_command import (
    live_stream_command,
)

from .bot_action_rules import BotAction

BOTS_MENU = ("&Bots",)
VIEW_MENU = ("&View",)
#: View → Chart, the chart in front's navigation (`EPIC-040` F1), as Market and Backtest have it.
CHART_MENU = ("&View", "C&hart")
_CONTRIBUTOR = "bots"
_PREFIX = "bots.bots"
#: The prefix of the commands that follow the selected bot's chart.
COMMAND_PREFIX = _PREFIX
#: The prefix of the chart commands (`chart_command_id`).
CHART_PREFIX = _PREFIX

NEW_BOT = f"{_PREFIX}.new_bot"
REFRESH_FILLS = f"{_PREFIX}.refresh_fills"
FIT_LEVELS = f"{_PREFIX}.fit_levels"
RETRY_CONNECTION = f"{_PREFIX}.retry_connection"
REFRESH_EXCHANGE = f"{_PREFIX}.refresh_exchange"
FIX_NEXT = f"{_PREFIX}.fix_next"
ARM_STRATEGY = f"{_PREFIX}.arm_strategy"
DISARM_STRATEGY = f"{_PREFIX}.disarm_strategy"
EXPORT_PLAN = f"{_PREFIX}.export_plan"
#: The centre's two tabs (`EPIC-040E`), as View commands.
LIVE_TAB = f"{_PREFIX}.live_tab"
BACKTEST_TAB = f"{_PREFIX}.backtest_tab"

#: Menu text per lifecycle action, in menu order; the toolbar ones are marked.
_LIFECYCLE: tuple[tuple[BotAction, str, bool, str | None], ...] = (
    (BotAction.SAVE, "&Save bot", True, "save"),
    # Decision D8 (`EPIC-034H`): saves the edits on screen, then starts.
    (BotAction.START, "Save and s&tart", True, "play"),
    (BotAction.PAUSE, "&Pause", True, "pause"),
    (BotAction.RESUME, "&Resume", True, "play"),
    (BotAction.CONFIRM_RESUME, "&Confirm resume", True, "circle-check-big"),
    (BotAction.STOP, "St&op…", True, "octagon"),
    (BotAction.DELETE, "&Delete bot", False, None),
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
        icon: str | None = None,
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
            icon=icon,
        )

    return (
        command(
            NEW_BOT, "&New bot…", on_toolbar=True, needs_input=True, icon="plus-circle"
        ),
        *(
            command(
                lifecycle_id(action),
                text,
                on_toolbar=on_toolbar,
                needs_input=text.endswith("…"),
                standard_shortcut="Save" if action is BotAction.SAVE else None,
                icon=icon,
            )
            for action, text, on_toolbar, icon in _LIFECYCLE
        ),
        # On the kind's own toolbar, not the mode's (HLD §11.2.3).
        *(
            command(kind_command.command_id, kind_command.text, on_toolbar=False)
            for kind_command in all_kind_commands()
        ),
        command(REFRESH_FILLS, "Refresh &fills", on_toolbar=False),
        command(FIT_LEVELS, "Fit &levels", on_toolbar=False),
        # `EPIC-034D`: reads the selected bot's venue account again.
        command(RETRY_CONNECTION, "Retry ven&ue account", on_toolbar=False),
        # `BOT-174`: asks the exchange again for the facts its readiness is judged on.
        command(REFRESH_EXCHANGE, "Refresh &exchange check", on_toolbar=False),
        # `EPIC-034H`: does the first fix the Plan's list of what is left offers.
        command(FIX_NEXT, "Fi&x next item", on_toolbar=False),
        live_stream_command(_CONTRIBUTOR, _PREFIX, route, BOTS_MENU, "Li&ve stream"),
        # Each asks which venue: M and I are free in the menu.
        command(ARM_STRATEGY, "Ar&m strategy…", on_toolbar=False, needs_input=True),
        command(
            DISARM_STRATEGY, "D&isarm strategy…", on_toolbar=False, needs_input=True
        ),
        # `BOT-176`: the bots as a `sew.bot-plan/1` file, for `bot apply` on a server;
        # every letter of its name was another command's access key; "A" moved from
        # Suggest from ATR (now "G", freed by Bollinger moving to "B") to this one.
        command(
            EXPORT_PLAN,
            "Export pl&an…",
            on_toolbar=True,
            needs_input=True,
            icon="download",
        ),
        # `EPIC-040E`: the centre's tabs by keyboard, named "tab" so they are not read as the
        # Backtest mode that View also lists; the Backtest tab is off for a bot whose kind or venue
        # it cannot replay, and says why (never hidden).
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=LIVE_TAB,
            text="&Live chart tab",
            menu_path=VIEW_MENU,
            mode=route,
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=BACKTEST_TAB,
            text="Bac&ktest tab",
            menu_path=VIEW_MENU,
            mode=route,
            shortcut="Ctrl+J",
        ),
        # `EPIC-040` F1: the chart in front's toolbar by keyboard - More timeframes… for the Live
        # chart's pinned timeframes and the workbench's interval row, and the Live chart's zoom.
        *chart_commands(_CONTRIBUTOR, CHART_PREFIX, route, CHART_MENU),
    )
