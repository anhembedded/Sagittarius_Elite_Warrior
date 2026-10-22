"""`BUG-267` - the real `bot list` and `bot show`, drawn at a terminal, colour every money figure by its sign.

@details The reports come from the real commands over the fixtures of `test_bot_earnings_reports.py`
and go through the terminal renderer, so a head that a hand-built test report spells differently
(`TOTAL PNL` for the real `TOTAL PNL (NET)`) cannot hide a missing colour.
"""

from __future__ import annotations

import argparse
import re

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import CliOutcome
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_printer import (
    IReportPrinter,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import Report
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_verbs import (
    ListBotsVerb,
    ShowBotVerb,
)
from Sagittarius_Elite_Warrior.src.shell.terminal_report_text import (
    TerminalAwareTextRenderer,
    TerminalState,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.text_report_renderer import (
    TextReportRenderer,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.test_bot_earnings_reports import (
    _args,
    _world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.verb_world import verb_world


class _KeepsTheReport(IReportPrinter):
    def __init__(self) -> None:
        self.report: Report | None = None

    def print_report(
        self, report: Report, args: argparse.Namespace
    ) -> CliOutcome | None:
        self.report = report
        return None


def _at_a_terminal(
    verb: ListBotsVerb | ShowBotVerb, columns: int, **args: object
) -> str:
    """A real report, drawn the way a terminal draws it, colour included."""
    kept = _KeepsTheReport()
    verb.run(_args(json=False, **args), verb_world(_world(), kept))
    assert kept.report is not None
    state = TerminalState(True, {"TERM": "xterm-256color"}, columns)
    return TerminalAwareTextRenderer(TextReportRenderer(), lambda: state).render(
        kept.report
    )


@pytest.mark.parametrize("columns", [200, 80])
def test_the_real_bot_list_colours_every_money_column_by_its_sign(columns: int) -> None:
    """The list's head is `TOTAL PNL (NET)`, so a colour looked up by the head text never met the
    real column: Total PnL was drawn plain while Grid profit and Realised were green. The figure
    is coloured by the column it is, whatever its head says, in the table and in the stacked
    layout of a narrow terminal."""
    text = _at_a_terminal(ListBotsVerb(), columns)

    green = re.findall(r"\x1b\[[0-9;]*32m([^\x1b]*)", text)
    red = re.findall(r"\x1b\[[0-9;]*31m([^\x1b]*)", text)
    assert any("1,234.50" in cell for cell in green), "Grid profit"
    assert any("20.00" in cell for cell in green), "Realised"
    assert any("30.00" in cell for cell in green), "Total PnL, a profit"
    assert any("-1,430.87" in cell for cell in red), "Total PnL, a loss"


def test_the_real_bot_show_colours_realised_grid_profit_and_total_pnl_by_their_sign() -> (
    None
):
    text = _at_a_terminal(ShowBotVerb(), 200, bot_id="ffffff")

    green = re.findall(r"\x1b\[[0-9;]*32m([^\x1b]*)", text)
    for figure in ("20.00", "1,234.50", "30.00"):
        assert any(figure in cell for cell in green), figure
