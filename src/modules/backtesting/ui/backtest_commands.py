"""The Backtest mode's commands (`EPIC-033D`): run, stop, and the report
tools.

Each is one `QAction` in the Backtest menu, scoped to the mode; Run (F7) and
Stop are also on its toolbar. Run and Stop were one button that changed its
text; as two commands each says what it does, and only the one that applies
is enabled. Stop, not Cancel: a run has side effects on the screen it is
filling (`ui-presentation-rule.md` §10). Save report… and the two that ask
for a file end with "…"; the comparison and Monte Carlo windows take none.

Qt-free, because `BacktestingModule.contribute()` imports it on a headless
run (`test_module_contribution_laziness.py`); the presenter's side is
`backtest_command_binding.py`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)

BACKTEST_MENU = ("&Backtest",)
_CONTRIBUTOR = "backtesting"
_PREFIX = "backtesting.backtest"

RUN = f"{_PREFIX}.run"
STOP = f"{_PREFIX}.stop"
SAVE_REPORT = f"{_PREFIX}.save_report"
IMPORT_REPORT = f"{_PREFIX}.import_report"
COMPARE_REPORTS = f"{_PREFIX}.compare_reports"
OUT_OF_SAMPLE = f"{_PREFIX}.out_of_sample"
MONTE_CARLO = f"{_PREFIX}.monte_carlo"


def backtest_commands(route: str) -> tuple[CommandContribution, ...]:
    """The commands of the Backtest mode at `route`, in menu order."""

    def command(
        command_id: str,
        text: str,
        *,
        on_toolbar: bool = False,
        shortcut: str | None = None,
        needs_input: bool = False,
    ) -> CommandContribution:
        return CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=command_id,
            text=text,
            menu_path=BACKTEST_MENU,
            mode=route,
            on_toolbar=on_toolbar,
            shortcut=shortcut,
            needs_input=needs_input,
        )

    return (
        command(RUN, "&Run backtest", on_toolbar=True, shortcut="F7"),
        command(STOP, "S&top", on_toolbar=True),
        command(SAVE_REPORT, "&Save report…", needs_input=True),
        command(IMPORT_REPORT, "&Import report…", needs_input=True),
        command(COMPARE_REPORTS, "&Compare reports…", needs_input=True),
        command(OUT_OF_SAMPLE, "In-sample vs &out-of-sample"),
        command(MONTE_CARLO, "&Monte Carlo"),
    )
