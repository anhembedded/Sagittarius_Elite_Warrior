"""The key may trade on the venue it is for (`EPIC-038F`).

A mainnet key's permission list is read back from the exchange
(`apiRestrictions`); a trading venue needs the permission for its own market, so
a read-only key fails. A testnet has no permission list: the only signal is the
account's own `canTrade` flag, and the finding says so rather than pretending
to a list it does not have.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.check_result import (
    CheckFinding,
    CheckStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.key_permission_reads import (
    mainnet_permissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.unreadable_connection import (
    unreadable_connection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.preflight.venue_checks import (
    PerVenueCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_permissions import (
    KeyPermissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)

_ENABLE_TRADING = (
    "Edit the key on the exchange and enable trading for this market "
    "(Spot & Margin Trading, or Futures), and keep withdrawal off."
)


class KeyPermissionsCheck(PerVenueCheck):
    check_id = "key-permissions"
    title = "API key may trade"

    def look_at(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> CheckFinding:
        if context.venue.is_mainnet:
            found = mainnet_permissions(self._reads, scope, name, context)
            if isinstance(found, CheckFinding):
                return found
            return _judge_list(name, context, found)
        return self._judge_flag(scope, name, context)

    def _judge_flag(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> CheckFinding:
        status = self._reads.connection(scope, name, context)
        if status.can_trade is None:
            return unreadable_connection(name, status, "whether the account may trade")
        if status.can_trade:
            return CheckFinding(
                name,
                CheckStatus.PASS,
                "the account reports trading allowed (a testnet has no key permission list)",
            )
        return CheckFinding(
            name,
            CheckStatus.FAIL,
            "the account reports trading not allowed",
            _ENABLE_TRADING,
        )


def _judge_list(
    name: str, context: VenueContext, permissions: KeyPermissions
) -> CheckFinding:
    futures = context.venue.market_type is MarketType.FUTURES_USD_M
    may_trade = permissions.can_trade_futures if futures else permissions.can_trade_spot
    market = "Futures" if futures else "Spot"
    if may_trade:
        return CheckFinding(name, CheckStatus.PASS, f"the key may trade {market}")
    reading = "read-only" if permissions.can_read else "unable to read"
    return CheckFinding(
        name,
        CheckStatus.FAIL,
        f"the key is {reading}: it may not trade {market}",
        _ENABLE_TRADING,
    )
