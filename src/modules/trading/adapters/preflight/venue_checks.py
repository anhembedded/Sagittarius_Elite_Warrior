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
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.core.contracts.i_preflight_check import (
    IPreflightCheck,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
    ReadPendingError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_reads import (
    VenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connection_failure_exit_code import (
    EXIT_CODE_FOR_FAILURE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_endpoints import (
    REQUEST_TIMEOUT_SECONDS,
)

#: What each exit code means for a finding. Only the two a connection failure can
#: reach; the mapping itself is `EXIT_CODE_FOR_FAILURE`, shared with `exchange-status`.
_CAUSE_OF_EXIT_CODE: dict[ExitCode, CheckCause] = {
    ExitCode.CONFIGURATION: CheckCause.CONFIGURATION,
    ExitCode.EXCHANGE: CheckCause.EXCHANGE,
}


def cause_of(kind: ConnectionFailureKind) -> CheckCause:
    """The cause a connection failure gives a finding: one rule, `exchange-status`'s."""
    return _CAUSE_OF_EXIT_CODE[EXIT_CODE_FOR_FAILURE[kind]]


NO_VENUE_IN_USE = "no venue has a key, so there is nothing to check"
NOT_ENABLED = "this venue is not served by this build"
PROVIDE_A_KEY = (
    "Provide a venue's key (see the credentials-present check), "
    "or name a venue with --venue."
)


#: A check reads the venue's account once, and the read is up to four requests
#: (ping, time, account, position mode), each bounded by the client's own timeout.
#: The deadline is longer than all four, so a dead route ends as the client's
#: `NETWORK` failure (exit 6) rather than as the runner's cut-off.
_READS_PER_CHECK = 4
_DEADLINE_MARGIN_SECONDS = 5.0


class PerVenueCheck(IPreflightCheck):
    deadline_seconds = (
        REQUEST_TIMEOUT_SECONDS * _READS_PER_CHECK + _DEADLINE_MARGIN_SECONDS
    )
    timeout_cause = CheckCause.EXCHANGE

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
        try:
            return self.look_at(scope, name, context)
        except ReadPendingError:
            return CheckFinding(
                name,
                CheckStatus.FAIL,
                "the exchange has not answered the read an earlier check started",
                "Check the VPS's outbound network and retry; the exchange is not responding.",
                CheckCause.EXCHANGE,
            )

    @abstractmethod
    def look_at(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> CheckFinding:
        """What this check finds for one enabled venue."""
