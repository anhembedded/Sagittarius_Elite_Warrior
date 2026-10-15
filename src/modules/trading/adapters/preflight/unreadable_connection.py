"""What a check says when the connection check gave it nothing to judge (`EPIC-038F`).

No key is the credentials check's finding, so here it is a `WARN` that the thing
was not measured (never a `PASS`: a false PASS is worse than none). A key the
exchange refused or could not be reached with is a `FAIL` carrying the cause the
exit code needs.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckFinding,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_checks import (
    cause_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)

_WORDS: dict[ConnectionFailureKind, tuple[str, str]] = {
    ConnectionFailureKind.NOT_CONFIGURED: (
        "no key is configured, so the exchange was not asked",
        "Provide the venue's API key; see the credentials check.",
    ),
    ConnectionFailureKind.BAD_SIGNATURE: (
        "the exchange could not verify the key's signature",
        "Copy the API secret again; it is usually mistyped or truncated.",
    ),
    ConnectionFailureKind.KEY_REJECTED: (
        "the exchange rejected the key",
        "See the outbound-address check for the three causes and how to tell them apart.",
    ),
    ConnectionFailureKind.NETWORK: (
        "the exchange could not be reached",
        "Check the VPS's outbound network, DNS and firewall; retry after a short wait.",
    ),
    ConnectionFailureKind.MAINTENANCE: (
        "the exchange answered with an error page, not an API reply",
        "Retry later; check the exchange's status page.",
    ),
    ConnectionFailureKind.CLOCK_SKEW: (
        "the exchange rejected the request's timestamp",
        "Sync the clock; see the clock-skew check.",
    ),
    ConnectionFailureKind.WITHDRAWAL_ENABLED: (
        "the key can withdraw funds",
        "Create a key without withdrawal; see the no-withdraw-permission check.",
    ),
    ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: (
        "the account is in Hedge Mode",
        "Switch the account to One-way mode.",
    ),
    ConnectionFailureKind.RATE_LIMITED: (
        "the exchange asked this host for a pause (a rate limit)",
        (
            "Wait for the pause to end and retry; if it recurs, a second process "
            "is sharing this IP's request weight."
        ),
    ),
}


#: Faults another check owns the FAIL for: a WARN here, so one fault is not several failures.
_REPORTED_ELSEWHERE = frozenset(
    {ConnectionFailureKind.NOT_CONFIGURED, ConnectionFailureKind.WITHDRAWAL_ENABLED}
)


def unreadable_connection(
    subject: str, status: ExchangeConnectionStatus, what: str
) -> CheckFinding:
    kind = status.failure
    if kind is None:
        return CheckFinding(
            subject,
            CheckStatus.WARN,
            f"{what} was not reported by the exchange",
            "Run preflight again; if it persists the exchange's answer changed.",
        )
    reason, remedy = _WORDS[kind]
    if kind in _REPORTED_ELSEWHERE:
        return CheckFinding(
            subject, CheckStatus.WARN, f"{what} was not measured: {reason}", remedy
        )
    return CheckFinding(
        subject,
        CheckStatus.FAIL,
        f"{what} could not be read: {reason}",
        remedy,
        cause_of(kind),
    )
