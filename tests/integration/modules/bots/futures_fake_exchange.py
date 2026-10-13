"""`EPIC-039C` - the composed app over the fake exchange's **Futures** testnet.

@details The Futures twin of `grid_fake_exchange.booted`. Nothing here is a hand-written
port: `create_app()` builds everything, the HTTP goes to the fake server, and the one
substitution is the websocket the fake does not have. The decision recorded in `EPIC-039C`:
**fills reach the app through the user-data stream's own handler**, fed from the fake's
queue (`OrderBookState.drain_user_data_events`) by `deliver()`, exactly as the Spot world
feeds `SpotUserDataStream`. A test that wants the stream silent, late or duplicated simply
does not call `deliver()`, calls it later, or sets `book.faults.duplicate_reports`.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_user_data_stream import (
    FuturesUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.kernel.app import App

from .grid_fake_exchange import FakeExchange, _let_background_work_finish, app_config

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from binance_fake_server import FakeServerUrls

FUTURES = TradingVenue.FUTURES_TESTNET
SYMBOL = "BTCUSDT"


@dataclass
class BootedFutures:
    """One boot of the composed app over the fake Futures exchange."""

    engine: App
    urls: FakeServerUrls
    scope: VenueTradingScope
    stream: FuturesUserDataStream

    def client(self) -> ITradingClient:
        """The venue's order client, live (the fake takes real orders only)."""
        return self.scope.ports.client_factory.create(OrderSubmissionMode.LIVE)

    def deliver(self) -> None:
        """Hands the stream what the exchange reported since the last call."""
        for event in self.urls.futures_book.drain_user_data_events():
            asyncio.run(self.stream._handle_message(event))

    def move_price(
        self, price: Decimal, *, fill_at_most: Decimal | None = None
    ) -> None:
        self.urls.futures_book.move_price(SYMBOL, price, fill_at_most=fill_at_most)
        self.deliver()


@contextmanager
def booted_futures(exchange: FakeExchange) -> Iterator[BootedFutures]:
    engine = create_app(app_config(exchange.tmp_path, FUTURES))
    container = engine.context.container
    engine.boot()
    scope = container.resolve(VenueTradingScopes).get(FUTURES)
    stream = scope.ports.user_data_stream
    assert isinstance(stream, FuturesUserDataStream)
    # `EPIC-039D` - the one thing opening the websocket would have done: an
    # `ACCOUNT_UPDATE` re-reads the position through the connection's own client.
    stream.use_client_of_a_connection(
        scope.ports.client_factory.create(OrderSubmissionMode.VALIDATE_ONLY)
    )
    try:
        yield BootedFutures(engine, exchange.urls, scope, stream)
    finally:
        _let_background_work_finish(container)
        engine.stop()
