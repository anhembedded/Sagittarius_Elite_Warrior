"""`EPIC-021J` §5 — the two order-lifecycle checks against real Futures
Testnet: a `VALIDATE_ONLY` dry-run is accepted, and a real minimal market
order fills and can be closed back to flat. Opt-in only — see
`conftest.py` for the two gates.

@details Waits on a *named condition* (position reconciled via
`get_positions()`), polled on a bounded loop — never a blind `sleep`
(`testing-rule.md` §2). This polls the REST position snapshot rather than
subscribing to `FuturesUserDataStream`'s own async websocket: standing up
that stream correctly inside a synchronous pytest function would be a
second, harder-to-verify implementation of the same wait, for no gain this
tier actually needs — the fill/close assertion cares about the exchange's
authoritative *position*, and `get_positions()` is that same authority
(`ADR §4`), whichever channel reports it first.

The round trip itself is `round_trips.futures_open_and_close`, shared with
`test_dual_venue_round_trip.py` (`EPIC-028N`). Minimal quantity throughout (`EPIC-021` epic's own worked example, `0.002`
BTC — comfortably above `MIN_NOTIONAL` at any real BTCUSDT price, aligned
to its real `0.001` step size). Cleans up in `finally`: a test that leaves
a position open corrupts every run after it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.tests.testnet.round_trips import (
    FUTURES_QUANTITY,
    SYMBOL,
    futures_open_and_close,
)


class _StaticCredentialsProvider(IExchangeCredentialsProvider):
    def __init__(self, credentials: ExchangeCredentials) -> None:
        self._credentials = credentials

    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(self._credentials, CredentialsSource.ENV)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise NotImplementedError("not used by this tier")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


def _build_client(
    testnet_credentials: ExchangeCredentials, mode: OrderSubmissionMode
) -> tuple[FuturesTradingClient, FuturesMetadataProvider]:
    session_factory = FuturesSessionFactory()
    metadata_provider = FuturesMetadataProvider(
        session_factory, InMemorySymbolOrderMetadataCache()
    )
    client = FuturesTradingClient(
        session_factory,
        _StaticCredentialsProvider(testnet_credentials),
        metadata_provider,
        mode,
    )
    return client, metadata_provider


def test_dry_run_is_accepted(testnet_credentials: ExchangeCredentials) -> None:
    client, metadata_provider = _build_client(
        testnet_credentials, OrderSubmissionMode.VALIDATE_ONLY
    )
    assert metadata_provider.get_or_fetch(SYMBOL) is not None

    order = Order(
        client_order_id=generate_client_order_id(),
        symbol=SYMBOL,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=FUTURES_QUANTITY,
    )

    # Raises OrderRejectedByExchangeError on rejection — a plain return
    # here already is the assertion.
    client.place_order(order)


def test_market_order_fills_and_closes(
    testnet_credentials: ExchangeCredentials,
) -> None:
    client, _ = _build_client(testnet_credentials, OrderSubmissionMode.LIVE)

    futures_open_and_close(client)
