"""`EPIC-038` D9 — one rule, one mapping: `preflight` and `exchange-status` exit alike.

Whether a restart can fix a fault decides the code: 5 when only the operator can
(no key, `-2015`, `-1022`, a key that can withdraw, Hedge Mode), 6 when the
fault is out there or will pass (network, maintenance, `-1021`).
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckFinding,
    CheckResult,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.operations.application.preflight_report import (
    preflight_outcome,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_checks import (
    cause_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connection_failure_exit_code import (
    EXIT_CODE_FOR_FAILURE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)

_K = ConnectionFailureKind


@pytest.mark.parametrize("kind", list(_K))
def test_a_failure_kind_exits_the_same_through_preflight_as_through_exchange_status(
    kind: ConnectionFailureKind,
) -> None:
    finding = CheckFinding("v", CheckStatus.FAIL, "r", "x", cause_of(kind))

    outcome = preflight_outcome((CheckResult.single("c", "c", finding),))

    assert outcome is not None
    assert outcome.code is EXIT_CODE_FOR_FAILURE[kind]


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        (_K.NOT_CONFIGURED, ExitCode.CONFIGURATION),
        (_K.KEY_REJECTED, ExitCode.CONFIGURATION),
        (_K.BAD_SIGNATURE, ExitCode.CONFIGURATION),
        (_K.WITHDRAWAL_ENABLED, ExitCode.CONFIGURATION),
        (_K.HEDGE_MODE_UNSUPPORTED, ExitCode.CONFIGURATION),
        (_K.NETWORK, ExitCode.EXCHANGE),
        (_K.MAINTENANCE, ExitCode.EXCHANGE),
        (_K.CLOCK_SKEW, ExitCode.EXCHANGE),
    ],
)
def test_the_rule_is_whether_a_restart_can_fix_it(
    kind: ConnectionFailureKind, code: ExitCode
) -> None:
    assert EXIT_CODE_FOR_FAILURE[kind] is code
