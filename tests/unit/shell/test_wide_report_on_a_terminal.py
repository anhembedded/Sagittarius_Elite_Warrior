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

    for whole in ("uie03d", "RECOVERING", "12.50", "-4.00", "61,000.00"):
        assert whole in plain.split()
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


_LIST_HEAD = (
    "ID", "NAME", "STATE", "VENUE", "SYMBOL", "GRID PROFIT", "CYCLES", "REALISED", "TOTAL PNL",
    "GRID STEP", "REASON",
)  # fmt: skip
_LIST_ROW = (
    "uie03d", "BTC grid", "RECOVERING", "binance", "BTCUSDT", "12.50", "3", "9.75", "-4.00",
    "150.00 (0.24%)", "exchange unreachable",
)  # fmt: skip


def _list_report() -> Report:
    return Report(
        "bot-list",
        1,
        {},
        (ReportSection(None, (_row(*_LIST_HEAD), _row(*_LIST_ROW)), has_header=True),),
    )


@pytest.mark.parametrize("columns", [120, 100, 80, 40, 30])
def test_an_eleven_column_list_never_loses_a_column_or_cuts_a_figure(columns):
    text = _renderer(_state(columns=columns)).render(_list_report())
    plain = _ANSI.sub("", text)

    assert _ESCAPE in text
    assert max(len(line) for line in plain.splitlines()) <= columns
    tokens = [t for t in plain.split() if not _BOX.search(t)]
    for word in (*_LIST_HEAD, *_LIST_ROW):
        for part in word.split():
            assert tokens.count(part) >= 1, (columns, part)
    assert sorted(t for t in tokens if t in {"12.50", "9.75", "-4.00", "uie03d", "RECOVERING"}) == [
        "-4.00", "12.50", "9.75", "RECOVERING", "uie03d",
    ]  # fmt: skip


@pytest.mark.parametrize("columns", [200, 80])
def test_the_realised_figure_takes_the_sign_colour_in_the_table_and_the_stacked_list(
    columns,
):
    """`BOT-231`: Realised is a money head in the table and a money label in the one block per bot
    a narrow terminal prints, so it is coloured like Grid profit and the total in both."""
    report = _list_report()
    text = _renderer(_state(columns=columns)).render(report)

    assert re.search(r"\x1b\[[0-9;]*32m[^\x1b]*12\.50", text)
    assert re.search(r"\x1b\[[0-9;]*32m[^\x1b]*9\.75", text)
    assert re.search(r"\x1b\[[0-9;]*31m[^\x1b]*-4\.00", text)


def test_a_word_wider_than_its_share_is_kept_whole_when_the_terminal_allows():
    order_id = "x-BTCUSDT-grid-level-0007-abcdef"
    report = Report(
        "demo",
        1,
        {},
        (
            ReportSection(
                None,
                (
                    _row("LEVEL", "STATE", "CLIENT ORDER ID", "NOTE"),
                    _row("7", "RESTING", order_id, "a long note " * 6),
                ),
                has_header=True,
            ),
        ),
    )

    plain = _ANSI.sub("", _renderer(_state(columns=70)).render(report))

    assert order_id in plain.split()
