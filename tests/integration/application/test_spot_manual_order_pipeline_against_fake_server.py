"""`EPIC-027O` — the manual order card's Spot BUY proof, at the same depth
`test_manual_order_pipeline_against_fake_server.py` already holds for
Futures: not "the presenter asked the dispatcher for the right command"
(the desks' order entry tests and `test_manual_order_intent.py` already
prove that), but what actually reaches the exchange once
`manual_order_intent_for()`'s BUY intent crosses `PreviewOrderQueryHandler`,
`SpotTradingClient`'s real order-payload mapping, and `python-binance`'s own
form encoding — and that the SAME `SpotAccountReader.check_connection()`
`HoldingsRefreshService`/`OrderFeed.holdingsChanged` reads afterwards
reflects the fill, proving the Holdings table's data source genuinely moves,
not just that an order was accepted.

@par What this proves, and what it deliberately does not
The fake exchange's `SpotAccountState` seeds a real, dust-clean BTC holding
before any order (`spot_account_state.py`'s own fixed initial balances), so
this reads BTC's `free` balance before and after rather than asserting a
holding merely exists — the only way to show a BUY *moved* the balance
`ITradingAccountReader.check_connection().holdings` reports, on real Spot
account-state mutation, not a la carte fixture data. It does not drive a
`qtbot` click or boot a window: the Spot desk's own Buy button is proven
end-to-end, from a real click through `ExecuteOrderCommandHandler` to the
fake exchange, by `test_spot_desk_against_fake_server.py`, and `manual_order_intent_for()`'s
BUY/SELL mapping is proven byte-for-byte at the unit level
(`test_manual_order_intent.py`) — this file's job is only the third leg,
same division of labour the Futures sibling test already states for itself.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client_factory import (
    SpotTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.handler import (
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.handler import (
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_fill_reporter import (
    FakeOrderFillReporter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimits,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
    manual_order_intent_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server

_SYMBOL = "BTCUSDT"
_QTY = Decimal("0.5")

#: `max_notional_per_order` well above 0.5 BTC @ 50,000 USDT reference
#: price — this task's own limits are not what this file exists to check
#: (`TradingLimitPolicy` already has its own dedicated coverage), same
#: reasoning `test_manual_order_pipeline_against_fake_server.py`'s own
#: `_LIMITS` states.
_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(50000),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(seconds=60),
)


class _FakeCredentialsProvider:
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise NotImplementedError("not used by this test")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


def test_a_manual_buy_click_reaches_the_wire_and_moves_the_reported_holding() -> None:
    """A human's BUY click on a Spot account: mapped by
    `manual_order_intent_for()` (flat, no position, no holding needed for
    LONG), dispatched through the exact same `ExecuteOrderCommand`/
    `ExecuteOrderCommandHandler` the strategy and Futures manual paths use,
    must both put a real order on the wire and be visible afterwards through
    `ITradingAccountReader.check_connection().holdings` — the same read
    `HoldingsRefreshService` polls and `OrderFeed.holdingsChanged` republishes
    for the desks' Holdings table."""
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = SpotSessionFactory()
        metadata_provider = SpotMetadataProvider(
            session_factory, InMemorySymbolOrderMetadataCache()
        )
        credentials_provider = _FakeCredentialsProvider()
        account_reader = SpotAccountReader(session_factory, credentials_provider)
        session_state = TradingSessionState()
        session_state.enable(set())
        trading_client_factory = SpotTradingClientFactory(
            session_factory,
            credentials_provider,
            metadata_provider,
            FakeOrderFillReporter(),
        )

        before = account_reader.check_connection()
        assert before.reachable is True
        btc_before = next(h for h in before.holdings or () if h.asset == "BTC")

        # Spot's `ITradingClient.get_positions()` always answers `[]`
        # (`SpotTradingClient`'s own docstring) — a flat LONG click needs no
        # freshly-read position or holding, only the market type.
        intent = manual_order_intent_for(
            ManualOrderDirection.LONG, None, TradingVenue.SPOT_TESTNET.market_type
        )
        context = venue_context(
            TradingVenue.SPOT_TESTNET,
            account_reader=account_reader,
            client_factory=trading_client_factory,
            metadata_provider=metadata_provider,
        )
        handler = ExecuteOrderCommandHandler(
            single_venue_scopes(context, session_state),
            PreviewOrderQueryHandler(FakeVenueContexts(context)),
            TradingLimitPolicy(_LIMITS),
            SessionReadiness(
                single_venue_scopes(context, session_state), RecordingPublisher()
            ),
        )
        result = handler.execute(
            ExecuteOrderCommand(
                order_request=PreviewOrderQuery(
                    venue=TradingVenue.SPOT_TESTNET,
                    symbol=_SYMBOL,
                    side=intent.side,
                    order_type=OrderType.MARKET,
                    quantity=_QTY,
                    reference_price=Decimal(50000),
                    reduce_only=intent.reduce_only,
                ),
                live=True,
            )
        )
        assert result.blocked is False, result.blocked_by

        after = account_reader.check_connection()
        btc_after = next(h for h in after.holdings or () if h.asset == "BTC")
        # The fake exchange's own fee convention (`spot_account_state.py`):
        # a BUY's commission is charged in the received (base) asset, so the
        # increase is the filled quantity minus that fee, never the raw qty.
        assert btc_after.free > btc_before.free
        assert btc_after.free <= btc_before.free + _QTY
        # `EPIC-028D` — the same read's summary: the BUY spent quote, so
        # what the desk can still spend went down.
        assert before.summary is not None
        assert after.summary is not None
        assert after.summary.available_balance < before.summary.available_balance


def test_a_second_manual_buy_on_the_same_symbol_is_not_blocked_by_a_position_limit() -> (
    None
):
    """`BUG-142` through the real Spot path: `SpotTradingClient` against the fake
    exchange, not a venue-agnostic double. Spot has no positions, so the first
    order must not mark the symbol open; the second reaches the wire and the
    reported BTC holding rises twice."""
    no_interval = TradingLimits(
        max_orders_per_session=20,
        max_notional_per_order=Decimal(50000),
        max_positions_per_symbol=1,
        min_order_interval=timedelta(0),
    )
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = SpotSessionFactory()
        metadata_provider = SpotMetadataProvider(
            session_factory, InMemorySymbolOrderMetadataCache()
        )
        credentials_provider = _FakeCredentialsProvider()
        account_reader = SpotAccountReader(session_factory, credentials_provider)
        session_state = TradingSessionState()
        session_state.enable(set())
        context = venue_context(
            TradingVenue.SPOT_TESTNET,
            account_reader=account_reader,
            client_factory=SpotTradingClientFactory(
                session_factory,
                credentials_provider,
                metadata_provider,
                FakeOrderFillReporter(),
            ),
            metadata_provider=metadata_provider,
        )
        handler = ExecuteOrderCommandHandler(
            single_venue_scopes(context, session_state),
            PreviewOrderQueryHandler(FakeVenueContexts(context)),
            TradingLimitPolicy(no_interval),
            SessionReadiness(
                single_venue_scopes(context, session_state), RecordingPublisher()
            ),
        )
        command = ExecuteOrderCommand(
            order_request=PreviewOrderQuery(
                venue=TradingVenue.SPOT_TESTNET,
                symbol=_SYMBOL,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=_QTY,
                reference_price=Decimal(50000),
            ),
            live=True,
        )

        def btc_free() -> Decimal:
            held = account_reader.check_connection().holdings or ()
            return next(h.free for h in held if h.asset == "BTC")

        start = btc_free()
        first = handler.execute(command)
        after_first = btc_free()
        second = handler.execute(command)

        assert first.blocked_by is None
        assert second.blocked_by is None
        assert btc_free() > after_first > start
        assert session_state.orders_sent_this_session == 2
        assert _SYMBOL not in session_state.known_open_symbols
