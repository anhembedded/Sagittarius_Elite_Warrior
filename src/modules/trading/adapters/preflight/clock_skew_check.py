"""This machine's clock against the exchange's (`EPIC-038F`).

Reads the skew the connection check already measures
(`ExchangeConnectionStatus.server_time_skew_ms`, local minus exchange) and
judges its size. Binance rejects a signed request whose timestamp is more than
1000 ms ahead of its server time (`-1021`, research R5), so a skew of 1000 ms
or more in either direction fails; above 500 ms warns, because a clock that far
off is drifting toward the limit. The boundaries: 500 passes, 501 warns, 999
warns, 1000 fails.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckCause,
    CheckFinding,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.unreadable_connection import (
    unreadable_connection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_checks import (
    PerVenueCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)

WARN_ABOVE_MS = 500
FAIL_AT_MS = 1000

SYNC_THE_CLOCK = (
    "Sync the clock: on Linux read `timedatectl status` (System clock synchronized: yes) "
    "or `chronyc tracking`; on Windows `w32tm /query /status`. A firewall that blocks "
    "outbound UDP 123 is a common reason a VPS has no time sync. Raising `recvWindow` "
    "is not a fix: it hides the drift."
)


class ClockSkewCheck(PerVenueCheck):
    check_id = "clock-skew"
    title = "Clock skew against the exchange"

    def look_at(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> CheckFinding:
        status = self._reads.connection(scope, name, context)
        skew = status.server_time_skew_ms
        if status.failure is ConnectionFailureKind.CLOCK_SKEW:
            known = "" if skew is None else f" (measured {skew} ms)"
            return CheckFinding(
                name,
                CheckStatus.FAIL,
                f"the exchange rejected a request as outside its time window{known}",
                SYNC_THE_CLOCK,
            )
        if skew is None:
            return unreadable_connection(name, status, "the clock skew")
        return _judge(name, skew)


def _judge(name: str, skew_ms: int) -> CheckFinding:
    size = abs(skew_ms)
    fact = f"local clock is {skew_ms:+d} ms from the exchange's"
    if size >= FAIL_AT_MS:
        return CheckFinding(
            name,
            CheckStatus.FAIL,
            f"{fact}: at or beyond the 1000 ms the exchange tolerates",
            SYNC_THE_CLOCK,
            CheckCause.NONE,
        )
    if size > WARN_ABOVE_MS:
        return CheckFinding(
            name, CheckStatus.WARN, f"{fact}: drifting toward the limit", SYNC_THE_CLOCK
        )
    return CheckFinding(name, CheckStatus.PASS, fact)
