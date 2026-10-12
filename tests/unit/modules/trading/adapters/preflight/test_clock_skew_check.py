"""`EPIC-038F` — clock skew: 500 passes, 501 warns, 999 warns, 1000 fails (research R5)."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.clock_skew_check import (
    ClockSkewCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_checks import (
    cause_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .preflight_world import reads_over, status, venue

FUTURES = TradingVenue.FUTURES_TESTNET


def _run(skew_ms: int | None, failure: ConnectionFailureKind | None = None):
    context = venue(FUTURES, status(FUTURES, skew_ms=skew_ms, failure=failure))
    return ClockSkewCheck(reads_over(context)).run(PreflightScope())


@pytest.mark.parametrize(
    ("skew_ms", "expected"),
    [
        (0, CheckStatus.PASS),
        (500, CheckStatus.PASS),
        (-500, CheckStatus.PASS),
        (501, CheckStatus.WARN),
        (-600, CheckStatus.WARN),
        (999, CheckStatus.WARN),
        (1000, CheckStatus.FAIL),
        (-1000, CheckStatus.FAIL),
        (1200, CheckStatus.FAIL),
    ],
)
def test_skew_of_600ms_warns_and_1200ms_fails(
    skew_ms: int, expected: CheckStatus
) -> None:
    assert _run(skew_ms).status is expected


def test_a_failing_skew_names_the_tools_and_says_recv_window_is_no_fix() -> None:
    remedy = _run(1200).findings[0].remedy

    for word in (
        "timedatectl status",
        "chronyc tracking",
        "w32tm /query /status",
        "recvWindow",
    ):
        assert word in remedy
    assert "not a fix" in remedy


def test_the_measured_skew_is_in_the_reason() -> None:
    assert "+600 ms" in _run(600).findings[0].reason


def test_the_exchange_rejecting_the_timestamp_fails_even_when_the_measure_is_small() -> (
    None
):
    result = _run(120, ConnectionFailureKind.CLOCK_SKEW)

    assert result.status is CheckStatus.FAIL
    assert result.cause is CheckCause.EXCHANGE, (
        "-1021 resyncs: exit 6, as exchange-status"
    )


def test_a_measured_skew_beyond_the_threshold_is_the_machines_fault_exit_four() -> None:
    assert _run(1200).cause is CheckCause.NONE


def test_an_unreachable_exchange_is_a_fail_with_the_exchange_cause() -> None:
    result = _run(None, ConnectionFailureKind.NETWORK)

    assert result.status is CheckStatus.FAIL
    assert result.cause is CheckCause.EXCHANGE


def test_no_key_means_the_skew_was_not_measured_which_is_a_warning_not_a_pass() -> None:
    result = _run(None, ConnectionFailureKind.NOT_CONFIGURED)

    assert result.status is CheckStatus.WARN
    assert "not measured" in result.findings[0].reason


def test_a_rejected_key_still_reports_the_skew_it_measured() -> None:
    result = _run(30, ConnectionFailureKind.KEY_REJECTED)

    assert result.status is CheckStatus.PASS


def test_every_failure_kind_has_a_cause() -> None:
    assert {cause_of(kind) for kind in ConnectionFailureKind} <= {
        CheckCause.CONFIGURATION,
        CheckCause.EXCHANGE,
    }


def test_the_exchange_is_asked_once_for_all_the_checks_of_one_run() -> None:
    context = venue(FUTURES)
    reads = reads_over(context)
    scope = PreflightScope()

    ClockSkewCheck(reads).run(scope)
    ClockSkewCheck(reads).run(scope)

    assert context.account_reader.checks == 1  # type: ignore[attr-defined]
