"""`EPIC-034` D5, D10 — keeping a mainnet venue's key, after checking it.

@details The check is the one the Connect step makes before every read of that
venue: the key gate, which refuses a key that can withdraw (D5). Only a key the gate
accepts is stored, so the app never keeps a credential that can move funds off the
exchange, and a key the exchange rejects is never stored to fail later. What it
stores it stores in the operating system's keyring and nowhere else (D10), under
the venue's own names, so a Spot key is never read for Futures.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.api_restrictions_key_gate import (
    ApiRestrictionsKeyGate,
    KeyPermissionsClients,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.key_permissions_client import (
    open_key_permissions_client,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def enrol_key(
    venue: TradingVenue,
    candidate: ExchangeCredentials,
    keep: IExchangeCredentialsProvider,
    clients: KeyPermissionsClients = open_key_permissions_client,
) -> ConnectFailure | None:
    """Checks `candidate` for `venue`; stores it through `keep` (the venue's own
    `MainnetCredentialsProvider`, whose store is the keyring) only when the gate
    accepted it.
    @return `None` when it was stored, else why it was refused.
    @raise ValueError `venue` is not a mainnet venue: a testnet key is kept in
    Settings, and a testnet key never goes in the keyring.
    @raise SecretStoreUnavailableError The key is fine but cannot be stored."""
    if not venue.is_mainnet:
        raise ValueError(f"{venue.name} is not a mainnet venue")
    refused = ApiRestrictionsKeyGate(venue, lambda: candidate, clients).check()
    if refused is None:
        keep.save_to_file(candidate.api_key, candidate.api_secret)
    return refused
