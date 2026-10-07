"""`EPIC-027P` — the one Spot Testnet round trip this tier proves: a small
MARKET BUY makes the target asset's holding appear (read the way
`HoldingsRefreshService`/the Holdings table do, through
`ITradingAccountReader.check_connection()`), then a MARKET SELL of exactly
what was received returns the holding to its pre-trade baseline. Opt-in
only — see `conftest.py` for the two gates.

@details Waits on a *named condition* (the reported holding, polled on a
bounded loop) — never a blind `sleep` (`testing-rule.md` §2), mirroring
`tests/testnet/test_order_lifecycle.py`'s own `_wait_until_position`. Spot
has no position to poll (`SpotTradingClient.get_positions()` always
answers `[]` — a Spot account's shape is a balance, not a position,
`EPIC-027K`); the authoritative fact this tier waits on is the same
`SpotAccountReader.check_connection().holdings` read the live Holdings
table itself is driven by, so a green run here is real evidence the same
mechanism the UI depends on moves for real money's worth on Spot Testnet
credentials.

The round trip itself is `round_trips.spot_buy_and_sell`, shared with
`test_dual_venue_round_trip.py` (`EPIC-028N`). Asserts invariants (the order left no open remainder — the real MARKET-
fills-immediately-on-Spot fact `test_fake_exchange_spot_routes.py`'s
fixture already encodes — and the holding returns to within one lot step
of its baseline), never prices. Cleans up in `finally`: a run that leaves a
surplus holding corrupts the baseline the next run reads.

`_QUANTITY` is deliberately small: `0.0002` BTC clears Binance Spot's
documented `NOTIONAL` minimum (5 USDT) at any realistic BTCUSDT price by a
wide margin, and is well above its `LOT_SIZE` step (`0.00001`, per
`test_fake_exchange_spot_routes.py`'s own fixture, itself read from
Binance's public filter documentation) — verification note: not
re-confirmed against a live call (egress to `*.binance.*` is policy-blocked
in this sandbox, same disclosure `SpotAccountReader`'s own module docstring
already makes); the user's own run of this tier is what confirms it against
the real, current Testnet filters.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.tests.testnet.round_trips import spot_buy_and_sell


class _StaticCredentialsProvider(IExchangeCredentialsProvider):
    def __init__(self, credentials: ExchangeCredentials) -> None:
        self._credentials = credentials

    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(self._credentials, CredentialsSource.ENV)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise NotImplementedError("not used by this tier")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


def _build_collaborators(
    spot_testnet_credentials: ExchangeCredentials,
) -> tuple[SpotTradingClient, SpotAccountReader, SpotMetadataProvider]:
    session_factory = SpotSessionFactory()
    metadata_provider = SpotMetadataProvider(
        session_factory, InMemorySymbolOrderMetadataCache()
    )
    credentials_provider = _StaticCredentialsProvider(spot_testnet_credentials)
    client = SpotTradingClient(
        session_factory,
        credentials_provider,
        metadata_provider,
        OrderSubmissionMode.LIVE,
    )
    account_reader = SpotAccountReader(session_factory, credentials_provider)
    return client, account_reader, metadata_provider


def test_market_buy_then_sell_returns_the_holding_to_baseline(
    spot_testnet_credentials: ExchangeCredentials,
) -> None:
    spot_buy_and_sell(*_build_collaborators(spot_testnet_credentials))
