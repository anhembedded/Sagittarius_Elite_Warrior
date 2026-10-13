"""The gate says in the log why `run` refused, and that it was told to skip (`EPIC-038D`).

`PreflightGate.admit` returned an outcome ("pre-flight failed: clock-skew") and kept
the findings to itself, which is right for `preflight` (it prints a report) and not
for a service whose only output is its log: an operator reading the journal after a
restart loop must find the reason and the remedy there.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.check_result import CheckStatus
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import PreflightScope
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_gate import (
    PreflightGate,
    PreflightPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_runner import (
    PreflightRunner,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.preflight_doubles import (
    ScriptedCheck,
    declared,
    resolver,
)

_LOGGER = "App.Operations.Preflight"


def _gate(*checks: ScriptedCheck) -> PreflightGate:
    return PreflightGate(PreflightRunner([declared(c) for c in checks], resolver()))


def test_a_refusal_logs_each_failed_finding_at_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    gate = _gate(ScriptedCheck("bad", CheckStatus.FAIL), ScriptedCheck("ok"))

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        refused = gate.admit(PreflightScope(), PreflightPolicy.ENFORCE)

    assert refused is not None
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "bad" in errors[0] and "bad said so" in errors[0]


def test_a_warning_finding_is_logged_at_warning_and_does_not_refuse(
    caplog: pytest.LogCaptureFixture,
) -> None:
    gate = _gate(ScriptedCheck("drifting", CheckStatus.WARN))

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        refused = gate.admit(PreflightScope(), PreflightPolicy.ENFORCE)

    assert refused is None
    assert [
        r.levelno for r in caplog.records if "drifting said so" in r.getMessage()
    ] == [logging.WARNING]


def test_skipping_the_gate_is_a_warning_that_says_no_check_ran(
    caplog: pytest.LogCaptureFixture,
) -> None:
    check = ScriptedCheck("bad", CheckStatus.FAIL)

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        skipped = _gate(check).admit(PreflightScope(), PreflightPolicy.SKIP)

    assert skipped is None
    assert check.runs == 0
    (warning,) = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert "--skip-preflight" in warning.getMessage()


def test_a_clean_pass_logs_no_warning_or_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        _gate(ScriptedCheck("ok")).admit(PreflightScope(), PreflightPolicy.ENFORCE)

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []
