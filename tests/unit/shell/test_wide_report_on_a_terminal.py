"""`BOT-198`: a report wider than the terminal still prints through `rich`, wrapped, nothing lost."""

from __future__ import annotations

import re

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.shell.terminal_report_text import (
    TerminalAwareTextRenderer,
    TerminalState,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.text_report_renderer import (
    TextReportRenderer,
)

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_BOX = re.compile("[─-╿]")
_ESCAPE = "\x1b"


def _row(*texts: str, widths: tuple[int, ...] = ()) -> ReportRow:
    return ReportRow(
        tuple(
            ReportCell(text, widths[i] if i < len(widths) else 0)
            for i, text in enumerate(texts)
        )
    )


def _state(
    *, tty: bool = True, env: dict[str, str] | None = None, columns: int = 200
) -> TerminalState:
    return TerminalState(tty, {"TERM": "xterm-256color", **(env or {})}, columns)


def _renderer(state: TerminalState) -> TerminalAwareTextRenderer:
    return TerminalAwareTextRenderer(TextReportRenderer(), lambda: state)


_LADDER = (
    "20 levels, buy 61,000.00 to 64,000.00, step 150.00 (0.24%), net step 0.19% after fees, "
    "recorded average 1.37 per cycle, capital 1,000.00 over 20 levels, "
    "lower edge 61,000.00, upper edge 64,000.00, stop loss 59,500.00, take profit 65,500.00"
)
_RECOVERY = (
    "exchange_unreachable: after 5 min clear, 1 of 3 used in 1 h, "
    "tells you after 10 min waiting (default layer)"
)


def _real_show_report() -> Report:
    """The shape of `bot show uie03d`: short label rows, a 200-character ladder row, recovery rows."""
    return Report(
        "bot-show",
        1,
        {},
        (
            ReportSection(
                "Bot uie03d",
                (
                    _row("Name", "BTC grid", widths=(12,)),
                    _row("State", "RECOVERING", widths=(12,)),
                    _row("Grid profit", "12.50", widths=(12,)),
                    _row("Total PnL", "-4.00", widths=(12,)),
                    _row("Ladder", _LADDER, widths=(32,)),
                    _row("Recovery", _RECOVERY, widths=(12,)),
                    _row(
                        "Recovery", _RECOVERY.replace("5 min", "15 min"), widths=(12,)
                    ),
                ),
            ),
        ),
    )


def _words(text: str) -> list[str]:
    return _ANSI.sub("", text).split()


@pytest.mark.parametrize("columns", [160, 100, 60, 40])
def test_a_report_wider_than_the_terminal_still_prints_through_rich_and_loses_nothing(
    columns,
):
    report = _real_show_report()
    assert (
        max(len(line) for line in TextReportRenderer().render(report).splitlines())
        > 200
    )

    text = _renderer(_state(columns=columns)).render(report)

    assert _ESCAPE in text
    assert text != TextReportRenderer().render(report)
    words = _words(text)
    expected = [
        w
        for section in report.layout
        for row in section.rows
        for cell in row.cells
        for w in cell.text.split()
    ]
    expected.extend(report.layout[0].title.split())
    assert sorted(words) == sorted(expected)
    assert max(len(_ANSI.sub("", line)) for line in text.splitlines()) <= columns


@pytest.mark.parametrize("columns", [160, 100])
def test_an_id_a_state_word_and_a_figure_are_never_cut_or_elided(columns):
    text = _renderer(_state(columns=columns)).render(_real_show_report())
    plain = _ANSI.sub("", text)

    for whole in ("uie03d", "RECOVERING", "12.50", "-4.00", "61,000.00", "64,000.00"):
        assert whole in plain.split() or any(whole in w for w in plain.split())
    assert "\u2026" not in plain
    assert re.search(r"\x1b\[[0-9;]*33m[^\x1b]*RECOVERING", text)
    assert re.search(r"\x1b\[[0-9;]*31m[^\x1b]*-4\.00", text)


def test_a_wide_table_wraps_its_free_text_column_and_keeps_the_figures_whole():
    reason = (
        "the exchange refused the request and the bot waits for it to come back " * 3
    )
    report = Report(
        "bot-list",
        1,
        {},
        (
            ReportSection(
                None,
                (
                    _row("ID", "STATE", "REASON"),
                    _row("a00001", "HALTED", reason.strip()),
                ),
                has_header=True,
            ),
        ),
    )

    text = _renderer(_state(columns=50)).render(report)
    lines = _ANSI.sub("", text).splitlines()

    assert len(lines) > 3
    assert all(len(line) <= 50 for line in lines)
    assert any(line.split()[:2] == ["a00001", "HALTED"] for line in lines)
    body = [w for w in _words(text) if not _BOX.search(w)]
    assert body == ["ID", "STATE", "REASON", "a00001", "HALTED", *reason.split()]


def test_plain_bytes_for_a_wide_report_are_the_same_whatever_the_columns():
    report = _real_show_report()

    for columns in (40, 100, 160):
        assert _renderer(_state(tty=False, columns=columns)).render(
            report
        ) == TextReportRenderer().render(report)
