"""The reads the trading pre-flight checks share, asked of the exchange once per run (`EPIC-038F`).

Four checks need the same connection check and two need the same key
permissions; each is a signed request, so a run asks once per venue and the
checks read the answer back through `PreflightScope.once`.

Everything here is read-only: `check_connection()` and the key probe read the
account, `resolve()` reads the key's source. Nothing places, tests or simulates
an order.

Which venues? The one the operator named with `--venue`, else every venue that
has a key. The build serves all four venues whatever the configuration says
(`resolve_trading_venues`), so "enabled" would make an operator who trades only
on the Spot Testnet fail for the three keys they never meant to have; and a
bot's own venue is not visible from here (`trading` does not depend on `bots`).
A venue with a key is a venue in use. If none has one, `named` is empty and
`CredentialsPresentCheck` says so as the failure it is.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.preflight_scope import (
    PreflightScope,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_environment import (
    EnvironmentVerdict,
    KeyEnvironment,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueReads:
    def __init__(self, contexts: IVenueContexts, probe: IKeyEnvironmentProbe) -> None:
        self._contexts = contexts
        self._probe = probe

    def named(self, scope: PreflightScope) -> tuple[str, ...]:
        """The venue names to check: `--venue`, else every venue that has a key."""
        if scope.venue is not None:
            return (scope.venue,)
        return tuple(
            venue.value
            for venue in self._contexts.enabled()
            if self.credentials(
                scope, venue.value, self._contexts.get(venue)
            ).credentials
            is not None
        )

    def context(self, name: str) -> VenueContext | None:
        """The venue's ports, or `None` when this configuration does not enable it."""
        try:
            return self._contexts.get(TradingVenue(name))
        except VenueNotEnabledError:
            return None

    def credentials(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> ResolvedCredentials:
        return scope.once(f"credentials:{name}", context.credentials_provider.resolve)

    def connection(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> ExchangeConnectionStatus:
        return scope.once(f"connection:{name}", context.account_reader.check_connection)

    def mainnet_verdict(
        self, scope: PreflightScope, name: str, context: VenueContext
    ) -> EnvironmentVerdict | None:
        """What mainnet says of the stored key (its permission list), or `None`
        when there is no key to ask with."""
        resolved = self.credentials(scope, name, context)
        credentials = resolved.credentials
        if credentials is None:
            return None
        return scope.once(
            f"verdict:{name}",
            lambda: self._probe.probe(KeyEnvironment.MAINNET, credentials),
        )
