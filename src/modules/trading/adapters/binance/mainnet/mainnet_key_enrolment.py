"""`EPIC-034E` (D5, D10) — keeping a read-only mainnet key, after checking it.

@details The check is the one the reader makes on every read: the key's
permissions first, a key that can withdraw refused. Only a key the reader
accepts is stored, so the app never keeps a credential that can move funds off
the exchange (D5), and a key the exchange rejects is never stored to fail later.
What it stores it stores in the operating system's keyring and nowhere else (D10).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_readonly_account_reader import (
    MainnetReadOnlyAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_readonly_credentials import (
    MainnetReadOnlyCredentials,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_credentials_resolver import (
    ICredentialsResolver,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_mainnet_read_client import (
    IMainnetReadSessionFactory,
)

#: The symbol the check reads the filters and price of; any listed one serves.
CHECK_SYMBOL = "BTCUSDT"


class _Candidate(ICredentialsResolver):
    """The one pair being checked, as if it were already the configured key."""

    def __init__(self, credentials: ExchangeCredentials) -> None:
        self._credentials = credentials

    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(self._credentials, CredentialsSource.ENV)


def enrol_key(
    candidate: ExchangeCredentials,
    clients: IMainnetReadSessionFactory,
    keep: MainnetReadOnlyCredentials,
) -> VenueAccountSnapshot | ConnectFailure:
    """Reads the account with `candidate`; stores it through `keep` only when
    the read succeeded, which a key that can withdraw never does.
    @raise SecretStoreUnavailableError The key is fine but cannot be stored."""
    answer = MainnetReadOnlyAccountReader(_Candidate(candidate), clients).read(
        CHECK_SYMBOL
    )
    if isinstance(answer, VenueAccountSnapshot):
        keep.save(candidate)
    return answer
