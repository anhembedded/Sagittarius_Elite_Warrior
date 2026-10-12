"""`EPIC-038F` — the report, the exit code and the gate that stops `run`."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckFinding,
    CheckResult,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_gate import (
    PreflightGate,
    PreflightPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_report import (
    CAUSE_EXIT_CODE,
    preflight_outcome,
    preflight_report,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_runner import (
    PreflightRunner,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.text_report_renderer import (
    TextReportRenderer,
)

from .preflight_doubles import ScriptedCheck, declared, resolver


def _result(
    check_id: str, status: CheckStatus, cause: CheckCause = CheckCause.NONE
) -> CheckResult:
    return CheckResult.single(
        check_id, check_id, CheckFinding("v", status, "because", "do this", cause)
    )


def test_every_cause_has_an_exit_code() -> None:
    assert set(CAUSE_EXIT_CODE) == set(CheckCause)


def test_nothing_failed_exits_zero_even_with_warnings() -> None:
    results = (_result("a", CheckStatus.PASS), _result("b", CheckStatus.WARN))

    assert preflight_outcome(results) is None


@pytest.mark.parametrize(
    ("cause", "code"),
    [
        (CheckCause.NONE, ExitCode.PREFLIGHT_FAILED),
        (CheckCause.CONFIGURATION, ExitCode.CONFIGURATION),
        (CheckCause.EXCHANGE, ExitCode.EXCHANGE),
    ],
)
def test_a_failure_exits_with_the_code_of_its_cause(
    cause: CheckCause, code: ExitCode
) -> None:
    outcome = preflight_outcome((_result("a", CheckStatus.FAIL, cause),))

    assert outcome is not None
    assert outcome.code is code


def test_missing_credentials_outrank_an_unreachable_exchange_and_a_plain_failure() -> (
    None
):
    results = (
        _result("disk", CheckStatus.FAIL),
        _result("net", CheckStatus.FAIL, CheckCause.EXCHANGE),
        _result("key", CheckStatus.FAIL, CheckCause.CONFIGURATION),
    )

    outcome = preflight_outcome(results)

    assert outcome is not None
    assert outcome.code is ExitCode.CONFIGURATION


def test_a_warning_never_carries_its_cause_into_the_exit_code() -> None:
    results = (_result("a", CheckStatus.WARN, CheckCause.CONFIGURATION),)

    assert preflight_outcome(results) is None


def test_the_payload_pins_its_keys() -> None:
    report = preflight_report((_result("a", CheckStatus.FAIL, CheckCause.EXCHANGE),))

    assert report.schema == "sew.preflight/1"
    assert set(report.payload) == {"summary", "checks"}
    assert report.payload["summary"] == {
        "pass": 0,
        "warn": 0,
        "fail": 1,
        "exit_code": int(ExitCode.EXCHANGE),
    }
    check = report.payload["checks"][0]  # type: ignore[index]
    assert set(check) == {"id", "title", "status", "origin", "findings"}
    assert set(check["findings"][0]) == {
        "subject",
        "status",
        "reason",
        "remedy",
        "cause",
    }


def test_the_text_report_shows_status_reason_and_the_remedy_of_a_failure() -> None:
    report = preflight_report(
        (_result("clock-skew", CheckStatus.FAIL), _result("disk", CheckStatus.PASS))
    )

    text = TextReportRenderer().render(report)

    assert "FAIL" in text
    assert "clock-skew" in text
    assert "fix: do this" in text
    assert text.count("fix:") == 1, "a PASS prints no remedy"


def test_run_refuses_to_start_when_preflight_fails_and_not_when_skipped() -> None:
    failing = ScriptedCheck("bad", CheckStatus.FAIL)
    gate = PreflightGate(PreflightRunner([declared(failing)], resolver()))

    refused = gate.admit(PreflightScope(), PreflightPolicy.ENFORCE)
    skipped = gate.admit(PreflightScope(), PreflightPolicy.SKIP)

    assert refused is not None
    assert refused.code is ExitCode.PREFLIGHT_FAILED
    assert skipped is None
    assert failing.runs == 1, "skipping the gate runs no check"


def test_run_starts_when_preflight_passes() -> None:
    gate = PreflightGate(PreflightRunner([declared(ScriptedCheck("ok"))], resolver()))

    assert gate.admit(PreflightScope(), PreflightPolicy.ENFORCE) is None
