"""Choosing a format from the arguments and printing a report in it (`EPIC-038B`)."""

from __future__ import annotations

import argparse
import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    Report,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.src.support.cli_host.report_output import (
    ReportFormatError,
    emit_report,
    select_format,
    wants_machine_output,
)

_REPORT = Report("demo", 1, {"x": 1}, (ReportSection(None, (ReportRow.of("hello"),)),))


def _args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**{"json": False, "format": None, **values})


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (_args(), "text"),
        (_args(json=True), "json"),
        (_args(format="json"), "json"),
        (_args(json=True, format="json"), "json"),
        (_args(format="text"), "text"),
        (argparse.Namespace(), "text"),
    ],
)
def test_the_format_the_arguments_ask_for(
    args: argparse.Namespace, expected: str
) -> None:
    assert select_format(args, ReportFormats.default()) == expected


def test_json_and_a_different_format_contradict_each_other() -> None:
    with pytest.raises(ReportFormatError, match="contradicts"):
        select_format(_args(json=True, format="text"), ReportFormats.default())


def test_an_unknown_format_names_the_ones_that_exist() -> None:
    with pytest.raises(ReportFormatError, match="text, json"):
        select_format(_args(format="xml"), ReportFormats.default())


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (_args(), False),
        (_args(format="text"), False),
        (_args(json=True), True),
        (_args(format="kv"), True),
    ],
)
def test_machine_output_is_anything_but_text(
    args: argparse.Namespace, expected: bool
) -> None:
    assert wants_machine_output(args) is expected


def test_emit_prints_the_rendering_and_returns_no_outcome(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert emit_report(_REPORT, _args(), ReportFormats.default()) is None
    assert capsys.readouterr().out == "hello\n"


def test_emit_in_json_prints_a_parsable_document(
    capsys: pytest.CaptureFixture[str],
) -> None:
    emit_report(_REPORT, _args(json=True), ReportFormats.default())

    assert json.loads(capsys.readouterr().out)["data"] == {"x": 1}


def test_an_unusable_format_prints_nothing_and_is_a_usage_outcome(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome = emit_report(_REPORT, _args(format="xml"), ReportFormats.default())

    assert outcome is not None
    assert outcome.code is ExitCode.USAGE
    assert "xml" in outcome.message
    assert capsys.readouterr().out == ""
