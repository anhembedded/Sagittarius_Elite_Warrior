"""The key cannot withdraw (`EPIC-038F`, research R4): **a key that can withdraw is a FAIL**.

The app reads and trades and never needs the permission, so holding a key that
could move funds off the exchange is a risk with no use. A mainnet key's flag is
read back from the exchange. A testnet has no withdrawal permission at all, and
the finding says that instead of a bare PASS.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckFinding,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.key_permission_reads import (
    mainnet_permissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_checks import (
    PerVenueCheck,
    cause_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)


class NoWithdrawPermissionCheck(PerVenueCheck):
    check_id = "no-withdraw-permission"
    title = "API key cannot withdraw"

    def look_at(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> CheckFinding:
        if not context.venue.is_mainnet:
            return CheckFinding(
                name,
                CheckStatus.PASS,
                "a testnet has no withdrawal permission, so its key cannot withdraw",
            )
        found = mainnet_permissions(self._reads, scope, name, context)
        if isinstance(found, CheckFinding):
            return found
        if found.can_withdraw:
            return CheckFinding(
                name,
                CheckStatus.FAIL,
                "the key can withdraw funds",
                "Create a key without withdrawal (leave 'Enable Withdrawals' off), "
                "store it in place of this one and delete this key on the exchange.",
                cause_of(ConnectionFailureKind.WITHDRAWAL_ENABLED),
            )
        return CheckFinding(name, CheckStatus.PASS, "the key cannot withdraw")
