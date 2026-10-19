"""`BOT-195`: `rich` draws the text report only for a person at a terminal; every other
reader gets the plain bytes, and `--json` is another renderer altogether."""

from __future__ import annotations

import argparse
import contextlib
import io
import re

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_renderer import (
    IReportRenderer,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.exchange_status_report import (
    exchange_status_report,
)
from Sagittarius_Elite_Warrior.src.shell.rich_text_report_renderer import (
    RichTextReportRenderer,
)
from Sagittarius_Elite_Warrior.src.shell.terminal_report_text import (
    ReportTooWideError,
    TerminalAwareTextRenderer,
    TerminalState,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.json_report_renderer import (
    JsonReportRenderer,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.text_report_renderer import (
    TextReportRenderer,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.src.support.cli_host.report_output import emit_report
from Sagittarius_Elite_Warrior.tests.unit.presentation.cli.golden_cases import (
    EXCHANGE_STATUS_CASES,
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


def _list_report() -> Report:
    head = ("ID", "NAME", "STATE", "GRID PROFIT", "TOTAL PNL")
    widths = (6, 12, 10, 12)
    return Report(
        "bot-list",
        1,
        {"bots": []},
        (
            ReportSection(
                None,
                (
                    _row(*head, widths=widths),
                    _row(
                        "a00001", "BTC grid", "RUNNING", "12.50", "13.00", widths=widths
                    ),
                    _row(
                        "a00002", "ETH grid", "HALTED", "-3.25", "-4.00", widths=widths
                    ),
                    _row(
                        "a00003", "SOL grid", "STOPPED", "0.00", "0.00", widths=widths
                    ),
                ),
                has_header=True,
            ),
        ),
    )


def _show_report() -> Report:
    return Report(
        "bot-show",
        1,
        {},
        (
            ReportSection(
                None,
                (
                    _row("Name", "BTC grid", widths=(12,)),
                    _row("State", "HALTED", widths=(12,)),
                    _row("Total PnL", "-4.00", widths=(12,)),
                    ReportRow.of("free text"),
                ),
            ),
        ),
    )


def _state(
    *, tty: bool = True, env: dict[str, str] | None = None, columns: int = 200
) -> TerminalState:
    return TerminalState(tty, {"TERM": "xterm-256color", **(env or {})}, columns)


def _renderer(state: TerminalState) -> TerminalAwareTextRenderer:
    return TerminalAwareTextRenderer(TextReportRenderer(), lambda: state)


def _reports() -> list[Report]:
    return [_list_report(), _show_report()] + [
        exchange_status_report(status) for status in EXCHANGE_STATUS_CASES.values()
    ]


@pytest.mark.parametrize(
    "state",
    [
        _state(tty=False),
        _state(env={"NO_COLOR": "1"}),
        _state(env={"NO_COLOR": ""}),
        _state(env={"TERM": "dumb"}),
    ],
    ids=["not-a-terminal", "no-color", "empty-no-color", "dumb"],
)
def test_every_reader_but_a_person_at_a_terminal_gets_the_plain_bytes(state):
    for report in _reports():
        assert _renderer(state).render(report) == TextReportRenderer().render(report)


def test_a_terminal_too_narrow_for_the_table_gets_the_plain_bytes():
    narrow = _renderer(_state(columns=20))

    assert narrow.render(_list_report()) == TextReportRenderer().render(_list_report())


def test_output_that_is_not_for_a_terminal_has_no_escape_and_no_box():
    text = _renderer(_state(tty=False)).render(_list_report())

    assert _ESCAPE not in text
    assert not _BOX.search(text)


def test_a_terminal_gets_a_table_with_the_words_and_signs_still_printed():
    text = _renderer(_state()).render(_list_report())
    plain = _ANSI.sub("", text)

    assert _ESCAPE in text
    for word in (
        "ID",
        "NAME",
        "STATE",
        "RUNNING",
        "HALTED",
        "STOPPED",
        "-3.25",
        "12.50",
    ):
        assert word in plain


def test_state_and_figure_colours_come_from_the_meaning_table():
    text = _renderer(_state()).render(_list_report())

    assert re.search(r"\x1b\[[0-9;]*32m[^\x1b]*RUNNING", text)
    assert re.search(r"\x1b\[[0-9;]*31m[^\x1b]*HALTED", text)
    assert re.search(r"\x1b\[[0-9;]*31m[^\x1b]*-3\.25", text)
    assert re.search(r"\x1b\[[0-9;]*32m[^\x1b]*12\.50", text)
    stopped = next(line for line in text.splitlines() if "STOPPED" in line)
    assert _ESCAPE not in stopped


def test_a_label_and_value_block_colours_state_and_loss_only():
    text = _renderer(_state()).render(_show_report())
    plain = _ANSI.sub("", text)

    assert re.search(r"\x1b\[[0-9;]*31m[^\x1b]*HALTED", text)
    assert re.search(r"\x1b\[[0-9;]*31m[^\x1b]*-4\.00", text)
    assert "Name" in plain
    assert "free text" in plain


def test_without_rich_the_plain_bytes_are_printed():
    def missing(columns: int) -> IReportRenderer:
        raise ModuleNotFoundError("No module named 'rich'", name="rich")

    renderer = TerminalAwareTextRenderer(
        TextReportRenderer(), lambda: _state(), missing
    )

    assert renderer.render(_list_report()) == TextReportRenderer().render(
        _list_report()
    )


def test_a_broken_rich_install_or_a_defect_is_not_hidden_behind_plain_text():
    def broken(columns: int) -> IReportRenderer:
        raise ModuleNotFoundError("No module named 'rich._x'", name="markdown_it")

    def defect(columns: int) -> IReportRenderer:
        raise ValueError("a defect in the renderer")

    for factory, error in ((broken, ModuleNotFoundError), (defect, ValueError)):
        renderer = TerminalAwareTextRenderer(
            TextReportRenderer(), lambda: _state(), factory
        )
        with pytest.raises(error):
            renderer.render(_list_report())


def test_a_table_with_no_header_is_not_given_one_because_its_words_are_upper_case():
    report = Report(
        "demo",
        1,
        {},
        (
            ReportSection(
                None,
                (
                    _row("BTCUSDT", "LONG", "RUNNING"),
                    _row("ETHUSDT", "SHORT", "HALTED"),
                ),
            ),
        ),
    )

    text = _renderer(_state()).render(report)

    assert "\u2500" not in text
    assert "\x1b[1m" not in text
    assert [line.split()[0] for line in _ANSI.sub("", text).splitlines()] == [
        "BTCUSDT",
        "ETHUSDT",
    ]


def test_json_is_the_same_bytes_at_a_terminal_and_not():
    def never(columns: int) -> IReportRenderer:
        raise AssertionError("rich was asked for on the JSON path")

    def render(state: TerminalState) -> str:
        text = TerminalAwareTextRenderer(TextReportRenderer(), lambda: state, never)
        formats = ReportFormats.default(text)
        json_renderer = formats.get("json")
        assert isinstance(json_renderer, JsonReportRenderer)
        args = argparse.Namespace(json=True, format=None)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert emit_report(_list_report(), args, formats) is None
        return out.getvalue()

    at_a_terminal = render(_state())
    assert at_a_terminal == render(_state(tty=False))
    assert '"schema": "sew.bot-list/1"' in at_a_terminal
    assert _ESCAPE not in at_a_terminal


def test_the_default_registry_still_has_the_plain_text_renderer():
    assert isinstance(ReportFormats.default().get("text"), TextReportRenderer)


def test_a_table_wider_than_the_terminal_is_refused_not_shortened():
    with pytest.raises(ReportTooWideError, match="columns needed"):
        RichTextReportRenderer(columns=20).render(_list_report())
