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

Minimal quantity throughout (`EPIC-021` epic's own worked example, `0.002`
BTC — comfortably above `MIN_NOTIONAL` at any real BTCUSDT price, aligned
to its real `0.001` step size). Cleans up in `finally`: a test that leaves
a position open corrupts every run after it.
"""

from __future__ import annotations

import time
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.futures_symbol_metadata_cache import (
    InMemoryFuturesSymbolMetadataCache,
)

_SYMBOL = "BTCUSDT"
_QUANTITY = Decimal("0.002")
_POLL_INTERVAL_S = 1.0
_TIMEOUT_S = 30.0


class _StaticCredentialsProvider:
    def __init__(self, credentials: ExchangeCredentials) -> None:
        self._credentials = credentials

    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(self._credentials, CredentialsSource.ENV)

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise NotImplementedError("not used by this tier")


def _wait_until_position(client: FuturesTradingClient, predicate) -> list[LivePosition]:
    """@brief Polls `get_positions()` until `predicate` accepts the
    result, or raises `TimeoutError` — the named condition this file's own
    docstring describes, not a blind sleep."""
    deadline = time.monotonic() + _TIMEOUT_S
    while time.monotonic() < deadline:
        positions = client.get_positions(_SYMBOL)
        if predicate(positions):
            return positions
        time.sleep(_POLL_INTERVAL_S)
    raise TimeoutError(
        f"{_SYMBOL} position did not reach the expected state within {_TIMEOUT_S}s"
    )


def _build_client(
    testnet_credentials: ExchangeCredentials, mode: OrderSubmissionMode
) -> tuple[FuturesTradingClient, FuturesMetadataProvider]:
    session_factory = ExchangeSessionFactory(MarketDataVenue.FUTURES_TESTNET)
    metadata_provider = FuturesMetadataProvider(
        session_factory, InMemoryFuturesSymbolMetadataCache()
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
    assert metadata_provider.get_or_fetch(_SYMBOL) is not None

    order = Order(
        client_order_id=generate_client_order_id(),
        symbol=_SYMBOL,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=_QUANTITY,
    )

    # Raises OrderRejectedByExchangeError on rejection — a plain return
    # here already is the assertion.
    client.place_order(order)


def test_market_order_fills_and_closes(
    testnet_credentials: ExchangeCredentials,
) -> None:
    client, _ = _build_client(testnet_credentials, OrderSubmissionMode.LIVE)

    entry = Order(
        client_order_id=generate_client_order_id(),
        symbol=_SYMBOL,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=_QUANTITY,
    )
    try:
        client.place_order(entry)
        positions = _wait_until_position(client, lambda p: len(p) == 1)
        assert positions[0].position_amt == _QUANTITY

        close = Order(
            client_order_id=generate_client_order_id(),
            symbol=_SYMBOL,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=_QUANTITY,
            reduce_only=True,
        )
        client.place_order(close)
        _wait_until_position(client, lambda p: len(p) == 0)
    finally:
        # Safety net: never leave a real position open for the next run,
        # regardless of which assertion above failed.
        remaining = client.get_positions(_SYMBOL)
        if remaining:
            position = remaining[0]
            client.place_order(
                Order(
                    client_order_id=generate_client_order_id(),
                    symbol=_SYMBOL,
                    side=OrderSide.SELL if position.position_amt > 0 else OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=abs(position.position_amt),
                    reduce_only=True,
                )
            )
