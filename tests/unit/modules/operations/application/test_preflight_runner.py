"""`EPIC-038F` — the runner isolates checks and knows none of them.

A check that raises, hangs or cannot be built is one FAIL named for that check;
the others still run. The runner is shown to be closed to change by adding a
check the runner's source has never heard of.
"""

from __future__ import annotations

import logging
import threading

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckOrigin,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    PreflightCheckDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_runner import (
    PreflightRunner,
)

from .preflight_doubles import ScriptedCheck, declared, never_returns, resolver


def _boom() -> None:
    raise RuntimeError("signed url https://x/?signature=SECRETSIG")


def test_a_check_that_raises_is_a_fail_and_the_rest_still_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    broken = ScriptedCheck("broken", action=_boom)
    after = ScriptedCheck("zafter")
    runner = PreflightRunner([declared(broken), declared(after)], resolver())

    with caplog.at_level(logging.WARNING, logger="App.Operations.Preflight"):
        results = runner.run(PreflightScope())

    by_id = {r.check_id: r for r in results}
    assert by_id["broken"].status is CheckStatus.FAIL
    assert by_id["broken"].origin is CheckOrigin.CRASHED
    assert by_id["zafter"].status is CheckStatus.PASS
    assert after.runs == 1
    # the report names the exception type, never its message (a signed URL lives there)
    assert "RuntimeError" in by_id["broken"].findings[0].reason
    assert "SECRETSIG" not in by_id["broken"].findings[0].reason
    assert any("[preflight]" in r.getMessage() for r in caplog.records)


def test_a_slow_check_is_cut_off(caplog: pytest.LogCaptureFixture) -> None:
    release = threading.Event()
    slow = ScriptedCheck("slow", action=never_returns(release), deadline_seconds=0.05)
    after = ScriptedCheck("zafter")
    runner = PreflightRunner([declared(slow), declared(after)], resolver())

    try:
        with caplog.at_level(logging.WARNING, logger="App.Operations.Preflight"):
            results = runner.run(PreflightScope())
    finally:
        release.set()

    assert results[0].origin is CheckOrigin.TIMED_OUT
    assert results[0].status is CheckStatus.FAIL
    assert results[1].status is CheckStatus.PASS


def test_a_new_check_appears_without_editing_the_runner() -> None:
    """The case the registry exists for: a check the runner has never heard of."""

    class OpenPortsCheck(ScriptedCheck):
        def __init__(self) -> None:
            super().__init__("open-ports", CheckStatus.WARN)

    runner = PreflightRunner(
        [declared(ScriptedCheck("a")), declared(OpenPortsCheck())], resolver()
    )

    results = runner.run(PreflightScope())

    assert [r.check_id for r in results] == ["a", "open-ports"]
    assert results[1].status is CheckStatus.WARN


def test_a_skipped_check_is_shown_as_a_warning_and_not_run() -> None:
    check = ScriptedCheck("disk")
    runner = PreflightRunner([declared(check)], resolver())

    (result,) = runner.run(PreflightScope(skip=frozenset({"disk"})))

    assert check.runs == 0
    assert result.origin is CheckOrigin.SKIPPED
    assert result.status is CheckStatus.WARN


def test_a_factory_that_raises_is_a_fail_for_its_check(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def factory(_resolver: object) -> ScriptedCheck:
        raise LookupError("not bound")

    runner = PreflightRunner(
        [PreflightCheckDescriptor("needs-port", factory, "trading")], resolver()
    )

    with caplog.at_level(logging.WARNING, logger="App.Operations.Preflight"):
        (result,) = runner.run(PreflightScope())

    assert result.check_id == "needs-port"
    assert result.status is CheckStatus.FAIL
    assert "trading" in result.findings[0].reason


def test_a_factory_that_builds_another_id_is_refused() -> None:
    runner = PreflightRunner(
        [
            PreflightCheckDescriptor(
                "declared-as", lambda _r: ScriptedCheck("built-as"), "m"
            )
        ],
        resolver(),
    )

    (result,) = runner.run(PreflightScope())

    assert result.status is CheckStatus.FAIL
    assert "built-as" in result.findings[0].reason


def test_the_memo_asks_once_per_run_and_again_in_the_next() -> None:
    asked: list[int] = []

    def ask() -> int:
        asked.append(1)
        return len(asked)

    first = PreflightScope()
    assert (first.once("k", ask), first.once("k", ask)) == (1, 1)
    assert PreflightScope().once("k", ask) == 2
