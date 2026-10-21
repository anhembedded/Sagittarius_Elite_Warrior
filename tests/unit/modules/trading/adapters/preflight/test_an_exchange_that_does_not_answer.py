"""`EPIC-038F` — an exchange that hangs ends as exit 6, and is asked once.

A dead route (a firewall DROP) makes the signed read outlive the check's
deadline. That must read as "the exchange is out of reach" (exit 6, which a
supervisor restarts after a delay) and not as a machine fault (exit 4, which it
never restarts); and the checks after the first must not start the same slow
read again.
"""

from __future__ import annotations

import contextlib
import threading

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckOrigin,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    PreflightCheckDescriptor,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
    ReadPendingError,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_report import (
    preflight_outcome,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_runner import (
    PreflightRunner,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.clock_skew_check import (
    ClockSkewCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.key_permissions_check import (
    KeyPermissionsCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.outbound_address_check import (
    OutboundAddressCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_checks import (
    PerVenueCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_credentials_provider import (
    FakeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    REQUEST_TIMEOUT_SECONDS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.preflight_doubles import (
    NoPorts,
)

from .preflight_world import reads_over, status

SPOT = TradingVenue.SPOT_TESTNET


class HangingReader(ITradingAccountReader):
    """Starts a connection check and never finishes it until released."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.started = 0

    def check_connection(self) -> ExchangeConnectionStatus:
        self.started += 1
        self.release.wait()
        return status(SPOT)

    def open_positions(self, priority=None):  # type: ignore[no-untyped-def]
        raise AssertionError("a pre-flight check reads no positions")


def _runner(reader: HangingReader, deadline_seconds: float) -> PreflightRunner:
    context = fake_venue_context(
        SPOT, account_reader=reader, credentials_provider=FakeCredentialsProvider()
    )
    reads = reads_over(context)
    descriptors = []
    for build in (ClockSkewCheck, KeyPermissionsCheck, OutboundAddressCheck):
        check: PerVenueCheck = build(reads)
        check.deadline_seconds = deadline_seconds
        descriptors.append(
            PreflightCheckDescriptor(check.check_id, lambda _r, c=check: c, "trading")
        )
    return PreflightRunner(descriptors, NoPorts())


def test_a_hanging_exchange_exits_six_not_four_and_is_asked_once() -> None:
    reader = HangingReader()
    try:
        results = _runner(reader, deadline_seconds=0.1).run(PreflightScope())
    finally:
        reader.release.set()

    assert [r.status for r in results] == [CheckStatus.FAIL] * 3
    assert results[0].origin is CheckOrigin.TIMED_OUT
    assert all(r.cause is CheckCause.EXCHANGE for r in results)
    outcome = preflight_outcome(results)
    assert outcome is not None
    assert outcome.code is ExitCode.EXCHANGE
    assert reader.started == 1, "the later checks must not start the same read again"


def test_the_deadline_of_an_exchange_check_exceeds_the_clients_own_timeout() -> None:
    assert PerVenueCheck.deadline_seconds > REQUEST_TIMEOUT_SECONDS * 4
    assert PerVenueCheck.timeout_cause is CheckCause.EXCHANGE


def test_a_read_in_flight_is_not_started_again_and_a_failed_one_may_be_retried() -> (
    None
):
    scope = PreflightScope()
    started: list[int] = []

    def slow() -> int:
        started.append(1)
        try:
            scope.once("k", slow)
        except ReadPendingError:
            return 1
        return 0

    assert scope.once("k", slow) == 1, "the nested ask saw the read pending"
    assert started == [1]

    def broken() -> int:
        raise RuntimeError("boom")

    with contextlib.suppress(RuntimeError):
        scope.once("j", broken)
    assert scope.once("j", lambda: 7) == 7
