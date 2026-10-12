"""The two renderers and the registry that holds them (`EPIC-038B`)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone

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
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.json_report_renderer import (
    JsonReportRenderer,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.text_report_renderer import (
    TextReportRenderer,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.presentation.cli.golden_cases import (
    EXCHANGE_STATUS_CASES,
)

_NOW = datetime(2026, 10, 12, 8, 30, 15, 999999, tzinfo=UTC)


def _report() -> Report:
    return Report(
        command="demo",
        version=3,
        payload={"venue": "futures_testnet", "balance": "1.50", "tags": ["a", None]},
        layout=(
            ReportSection(
                "Demo",
                (
                    ReportRow(
                        (ReportCell("Venue:", 8), ReportCell("fx", 4), ReportCell("ok"))
                    ),
                    ReportRow.of("  free text"),
                ),
            ),
        ),
    )


def test_the_text_renderer_pads_each_cell_and_joins_them_with_one_space() -> None:
    assert (
        TextReportRenderer().render(_report()) == "Demo\nVenue:   fx   ok\n  free text"
    )


def test_an_empty_trailing_cell_leaves_its_separator() -> None:
    """The old hand-built lines ended in a space when the last figure was empty;
    the golden fixtures pin it, so the renderer must reproduce it."""
    row = ReportRow((ReportCell("a", 3), ReportCell("")))
    report = Report("demo", 1, {}, (ReportSection(None, (row,)),))

    assert TextReportRenderer().render(report) == "a   "


def test_the_json_envelope_has_schema_time_and_data() -> None:
    text = JsonReportRenderer(clock=lambda: _NOW).render(_report())

    assert json.loads(text) == {
        "schema": "sew.demo/3",
        "generated_at": "2026-10-12T08:30:15Z",
        "data": {"venue": "futures_testnet", "balance": "1.50", "tags": ["a", None]},
    }


def test_the_json_time_is_utc_whatever_zone_the_clock_is_in() -> None:
    local = _NOW.astimezone(timezone(timedelta(hours=7)))

    text = JsonReportRenderer(clock=lambda: local).render(_report())

    assert json.loads(text)["generated_at"] == "2026-10-12T08:30:15Z"


def test_the_json_renderer_ignores_the_layout() -> None:
    bare = Report("demo", 3, _report().payload, ())

    assert JsonReportRenderer(clock=lambda: _NOW).render(bare) == JsonReportRenderer(
        clock=lambda: _NOW
    ).render(_report())


class _KeyValueRenderer(IReportRenderer):
    """The third renderer: one `key=value` line, written for this test only."""

    def render(self, report: Report) -> str:
        return " ".join(f"{key}={value}" for key, value in report.payload.items())


def test_a_new_renderer_registers_without_editing_a_command() -> None:
    """Open/closed, run: the renderer is one class and one `register` call, and
    the report is the one an existing command builds, untouched."""
    formats = ReportFormats.default()
    formats.register("kv", _KeyValueRenderer())

    renderer = formats.get("kv")
    assert renderer is not None
    line = renderer.render(
        exchange_status_report(EXCHANGE_STATUS_CASES["futures_success_without_summary"])
    )
    assert line.startswith("venue=futures_testnet reachable=True failure=None")
    assert formats.names() == ("text", "json", "kv")


def test_a_format_name_is_registered_once() -> None:
    formats = ReportFormats.default()

    with pytest.raises(ValueError, match="already registered"):
        formats.register("json", JsonReportRenderer())


@pytest.mark.parametrize("name", ["", "JSON", "two words", " json"])
def test_a_format_name_is_a_lowercase_word(name: str) -> None:
    with pytest.raises(ValueError, match="lowercase word"):
        ReportFormats().register(name, TextReportRenderer())


def test_an_unregistered_format_is_none() -> None:
    assert ReportFormats.default().get("yaml") is None
