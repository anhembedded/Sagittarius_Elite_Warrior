"""The `status` command: its report, its exit codes and `--watch` (`EPIC-038C`)."""

from __future__ import annotations

import argparse
import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    RECORDED_STATES_NOTE,
)
from Sagittarius_Elite_Warrior.src.modules.operations.cli.status_cli_handler import (
    run_status,
)
from Sagittarius_Elite_Warrior.src.shell.report_printer import ReportPrinter
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.status_world import (
    INTERVAL_S,
    HostStatusDispatcher,
    StubProbe,
    StubSource,
    seeded_bots,
    snapshot_aged,
)

_PRINTER = ReportPrinter(ReportFormats.default())
_HOST_KEYS = {
    "state", "reason", "lock_held", "snapshot_age_s", "host_state", "pid",
    "app_version", "started_at", "written_at", "interval_s",
}  # fmt: skip
_PAYLOAD_KEYS = {
    "host", "sections", "unavailable_sections", "app_running", "bots", "unreadable",
    "counts",
}  # fmt: skip
_UNAVAILABLE = {"status": "unavailable", "reason": "raised ValueError"}


def _args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(
        **{"json": True, "format": None, "watch": False, "interval": 10, **values}
    )


def _run(
    held: bool, source: StubSource, capsys: pytest.CaptureFixture[str], **values: object
) -> tuple[ExitCode, str]:
    dispatcher = HostStatusDispatcher(StubProbe(held), source, seeded_bots())
    outcome = run_status(_args(**values), dispatcher, _PRINTER)
    return (
        ExitCode.SUCCESS if outcome is None else outcome.code
    ), capsys.readouterr().out


def test_status_exit_codes_are_0_10_11(capsys: pytest.CaptureFixture[str]) -> None:
    healthy = StubSource(snapshot_aged(INTERVAL_S))
    one_section_down = StubSource(
        snapshot_aged(INTERVAL_S, {"bots": {"total": 2}, "trading": _UNAVAILABLE})
    )

    assert _run(True, healthy, capsys)[0] is ExitCode.SUCCESS
    assert _run(False, healthy, capsys)[0] is ExitCode.HOST_NOT_RUNNING
    assert _run(True, StubSource(snapshot_aged(10 * INTERVAL_S)), capsys)[0] is (
        ExitCode.HOST_UNHEALTHY
    )
    assert _run(True, StubSource(None), capsys)[0] is ExitCode.HOST_UNHEALTHY
    assert _run(True, one_section_down, capsys)[0] is ExitCode.HOST_UNHEALTHY


def test_the_status_payload_keys_are_pinned(capsys: pytest.CaptureFixture[str]) -> None:
    _, out = _run(True, StubSource(snapshot_aged(1)), capsys)

    document = json.loads(out)
    assert document["schema"] == "sew.status/1"
    assert set(document["data"]) == _PAYLOAD_KEYS
    assert set(document["data"]["host"]) == _HOST_KEYS
    assert document["data"]["host"]["state"] == "running"
    assert document["data"]["counts"] == {"RUNNING": 1, "HALTED": 1}


def test_a_section_a_module_contributes_reaches_status_and_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = StubSource(
        snapshot_aged(1, {"bots": {"total": 2}, "fourth": {"anything": 7}})
    )

    _, out = _run(True, source, capsys)

    assert json.loads(out)["data"]["sections"]["fourth"] == {"anything": 7}
    _, text = _run(True, source, capsys, json=False)
    assert "fourth" in text
    assert '"anything": 7' in text


def test_an_unavailable_section_is_named(capsys: pytest.CaptureFixture[str]) -> None:
    source = StubSource(snapshot_aged(1, {"trading": _UNAVAILABLE}))

    _, out = _run(True, source, capsys)

    assert json.loads(out)["data"]["unavailable_sections"] == ["trading"]


def test_a_missing_snapshot_is_null_not_invented(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out = _run(False, StubSource(None), capsys)

    host = json.loads(out)["data"]["host"]
    assert host["state"] == "not running"
    assert host["written_at"] is None
    assert host["pid"] is None


def test_an_unknown_format_is_a_usage_error_and_prints_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out = _run(True, StubSource(None), capsys, json=False, format="yaml")

    assert code is ExitCode.USAGE
    assert out == ""


def test_watch_repeats_the_same_report_until_interrupted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    waits: list[float] = []

    def interrupt_on_third(seconds: float) -> None:
        waits.append(seconds)
        if len(waits) == 3:
            raise KeyboardInterrupt

    dispatcher = HostStatusDispatcher(StubProbe(False), StubSource(None), seeded_bots())

    outcome = run_status(
        _args(watch=True, interval=7, json=False),
        dispatcher,
        _PRINTER,
        interrupt_on_third,
    )

    assert outcome is None  # Ctrl-C ends a watch with 0, whatever it saw
    assert waits == [7, 7, 7]
    assert capsys.readouterr().out.count("not running") == 3


def test_watch_refuses_an_interval_below_one_second(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out = _run(True, StubSource(None), capsys, watch=True, interval=0)

    assert code is ExitCode.USAGE
    assert out == ""


def test_status_text_says_the_bot_states_are_recorded_when_no_host_runs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out = _run(False, StubSource(None), capsys, json=False)

    assert RECORDED_STATES_NOTE in out
    _, running = _run(True, StubSource(snapshot_aged(1)), capsys, json=False)
    assert RECORDED_STATES_NOTE not in running
