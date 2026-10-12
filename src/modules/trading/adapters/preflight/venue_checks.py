"""The shape every per-venue trading check shares (`EPIC-038F`).

A check looks at each venue and gives one finding per venue. This base class
owns the loop, the two situations every check meets before it can look at
anything (no venue enabled, the named venue not enabled), and the one place a
`ConnectionFailureKind` becomes a `CheckCause`; a subclass writes
`look_at(scope, name, context)` and nothing else.
"""

from __future__ import annotations

from abc import abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckFinding,
    CheckResult,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_preflight_check import (
    IPreflightCheck,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_reads import (
    VenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)

#: Complete on purpose (`test_every_failure_kind_has_a_cause`): the key is the
#: operator's to fix (5, never retried) or the exchange is out of reach (6,
#: retried); everything else is a plain failure (4).
CAUSE_OF_FAILURE: dict[ConnectionFailureKind, CheckCause] = {
    ConnectionFailureKind.NOT_CONFIGURED: CheckCause.CREDENTIALS,
    ConnectionFailureKind.BAD_SIGNATURE: CheckCause.CREDENTIALS,
    ConnectionFailureKind.KEY_REJECTED: CheckCause.CREDENTIALS,
    ConnectionFailureKind.NETWORK: CheckCause.EXCHANGE,
    ConnectionFailureKind.MAINTENANCE: CheckCause.EXCHANGE,
    ConnectionFailureKind.CLOCK_SKEW: CheckCause.NONE,
    ConnectionFailureKind.WITHDRAWAL_ENABLED: CheckCause.NONE,
    ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: CheckCause.NONE,
}

NO_VENUE_IN_USE = "no venue has a key, so there is nothing to check"
NOT_ENABLED = "this venue is not served by this build"
PROVIDE_A_KEY = (
    "Provide a venue's key (see the credentials-present check), "
    "or name a venue with --venue."
)


class PerVenueCheck(IPreflightCheck):
    def __init__(self, reads: VenueReads) -> None:
        self._reads = reads

    def run(self, scope: PreflightScope) -> CheckResult:
        names = self._reads.named(scope)
        if not names:
            return self.when_no_venue_is_in_use()
        return CheckResult(
            self.check_id, self.title, tuple(self._finding(scope, n) for n in names)
        )

    def when_no_venue_is_in_use(self) -> CheckResult:
        """Nothing has a key: a warning that nothing was checked (never a pass)."""
        return CheckResult.single(
            self.check_id,
            self.title,
            CheckFinding("", CheckStatus.WARN, NO_VENUE_IN_USE, PROVIDE_A_KEY),
        )

    def _finding(self, scope: PreflightScope, name: str) -> CheckFinding:
        context = self._reads.context(name)
        if context is None:
            return CheckFinding(name, CheckStatus.FAIL, NOT_ENABLED, PROVIDE_A_KEY)
        return self.look_at(scope, name, context)

    @abstractmethod
    def look_at(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> CheckFinding:
        """What this check finds for one enabled venue."""
