"""A mainnet key's permission list, or the finding that says why there is none (`EPIC-038F`).

Both permission checks ask the same question of the same signed read
(`GET /sapi/v1/account/apiRestrictions`, through the existing
`IKeyEnvironmentProbe`), so the translation of the exchange's other answers is
written once. A testnet has no such endpoint; its checks do not come here.
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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_checks import (
    cause_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_reads import (
    VenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    KeyStanding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_permissions import (
    KeyPermissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)


def mainnet_permissions(
    reads: VenueReads, scope: PreflightScope, name: str, context: VenueContext
) -> KeyPermissions | CheckFinding:
    verdict = reads.mainnet_verdict(scope, name, context)
    if verdict is None:
        return CheckFinding(
            name,
            CheckStatus.WARN,
            "the key's permissions were not read: no key is configured",
            "Provide the venue's key; see the credentials check.",
        )
    if verdict.standing is KeyStanding.ACCEPTED and verdict.permissions is not None:
        return verdict.permissions
    if verdict.standing in (KeyStanding.UNKNOWN, KeyStanding.REFUSED):
        return CheckFinding(
            name,
            CheckStatus.FAIL,
            f"the exchange would not tell what the key may do: {verdict.reason}",
            "See the outbound-address check for the three causes and how to tell them apart.",
            CheckCause.CONFIGURATION,
        )
    cause = (
        cause_of(verdict.failure)
        if verdict.failure is not None
        else CheckCause.EXCHANGE
    )
    return CheckFinding(
        name,
        CheckStatus.FAIL,
        "the key's permissions could not be read: the exchange gave no usable answer",
        "Check the VPS's outbound network and retry; see the clock-skew check if the clock is off.",
        cause,
    )
