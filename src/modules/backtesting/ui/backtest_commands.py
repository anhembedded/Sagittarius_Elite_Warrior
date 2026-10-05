"""The Backtest mode's commands (`EPIC-033D`): run, stop, and the report
tools.

Each is one `QAction` in the Tools menu, where HLD §11.2.3 puts Run backtest
and Stop backtest, scoped to the mode; those two are also on its toolbar. The
report tools are not in the catalogue yet (`EPIC-033L` designs the mode) and
sit beside them until then. Run and Stop were one button that changed its
text; as two commands each says what it does, and only the one that applies
is enabled. Stop, not Cancel: a run has side effects on the screen it is
filling (`ui-presentation-rule.md` §10). Save report…, Export trades… (the
trades the Trades panel lists, as CSV; a button on that panel until
`EPIC-033L`) and the two that ask for a file end with "…"; the comparison and Monte Carlo windows take none.

Qt-free, because `BacktestingModule.contribute()` imports it on a headless
run (`test_module_contribution_laziness.py`); the presenter's side is
`backtest_command_binding.py`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)

#: The shell's Tools menu (it already holds &Options, so the access keys
#: below avoid O).
BACKTEST_MENU = ("&Tools",)
_CONTRIBUTOR = "backtesting"
_PREFIX = "backtesting.backtest"

RUN = f"{_PREFIX}.run"
STOP = f"{_PREFIX}.stop"
SAVE_REPORT = f"{_PREFIX}.save_report"
IMPORT_REPORT = f"{_PREFIX}.import_report"
COMPARE_REPORTS = f"{_PREFIX}.compare_reports"
OUT_OF_SAMPLE = f"{_PREFIX}.out_of_sample"
MONTE_CARLO = f"{_PREFIX}.monte_carlo"
EXPORT_TRADES = f"{_PREFIX}.export_trades"


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
        command(STOP, "&Stop backtest", on_toolbar=True),
        command(SAVE_REPORT, "Sa&ve report…", needs_input=True),
        command(IMPORT_REPORT, "&Import report…", needs_input=True),
        command(COMPARE_REPORTS, "Com&pare reports…", needs_input=True),
        command(OUT_OF_SAMPLE, "In-sample vs out-of-sa&mple"),
        command(MONTE_CARLO, "Monte Car&lo"),
        command(EXPORT_TRADES, "Export &trades…", needs_input=True),
    )
