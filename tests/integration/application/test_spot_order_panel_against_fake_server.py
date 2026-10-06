"""`EPIC-028H` — the order panel's Spot Buy, from the panel's own submit to
the exchange and back: the holding the account reports moves. `EPIC-028O`
adds the quote-sized market buy, the stop-limit that rests, the BBO button
reading the venue's book and the app's notional limit read at load.

@details What the unit tests cannot show: that the panel's terms are the
venue's real filters and fees (`GetSymbolOrderRulesQuery`,
`GetCommissionRateQuery`), and that preview → confirm → submit reaches the
wire through the real handlers, `SpotTradingClient` and `python-binance`,
on the fake exchange. The dispatcher here routes each query and command to
its real handler; the container's own wiring is `test_composition_root.py`'s.
The dialog is a recorded "Yes" and the worker pool runs inline, the two
things a test cannot drive for real.
"""

from __future__ import annotations

import concurrent.futures
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_reader import (
    SpotAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_book_ticker_reader import (
    SpotBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_commission_rate_reader import (
    SpotCommissionRateReader,
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
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.account_snapshot_service import (
    AccountSnapshotService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order import (
    ExecuteOrderCommand,
    ExecuteOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.order_entry_terms_service import (
    OrderEntryTermsService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.order_submission_service import (
    OrderSubmissionService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_best_bid_ask import (
    GetBestBidAskQuery,
    GetBestBidAskQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_commission_rate import (
    GetCommissionRateQuery,
    GetCommissionRateQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
    GetExchangeConnectionStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
    GetOpenPositionsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_notional_limit import (
    GetOrderNotionalLimitQuery,
    GetOrderNotionalLimitQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_symbol_order_rules import (
    GetSymbolOrderRulesQuery,
    GetSymbolOrderRulesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimits,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_confirmation import (
    OrderConfirmation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_presenter import (
    OrderEntryPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server

_SPOT = TradingVenue.SPOT_TESTNET
_SYMBOL = "BTCUSDT"
#: The fake exchange's `BTCUSDT` last price (`spot_account_state.py`).
_FAKE_LAST_PRICE = Decimal(50000)
_LIMITS = TradingLimits(
    max_orders_per_session=20,
    max_notional_per_order=Decimal(5000),
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


class _RoutingDispatcher(ICommandDispatcher):
    """Each query or command to its real handler."""

    def __init__(self, handlers: dict[type, Any]) -> None:
        self._handlers = handlers

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        return self._handlers[handler_class].execute(input_dto)


class _InlineThreadManager(IThreadManager):
    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None


@dataclass
class _SpotPanel:
    view_model: OrderEntryViewModel
    presenter: OrderEntryPresenter
    asked: list[OrderConfirmation]


@contextmanager
def _spot_panel_on_fake_server() -> Iterator[_SpotPanel]:
    """The Spot desk's panel, its ports answered by the real handlers on the
    fake exchange, showing `BTCUSDT` at the fake's last price."""
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        session_factory = SpotSessionFactory()
        credentials = _FakeCredentialsProvider()
        metadata_provider = SpotMetadataProvider(
            session_factory, InMemorySymbolOrderMetadataCache()
        )
        context = replace(
            venue_context(
                _SPOT,
                account_reader=SpotAccountReader(session_factory, credentials),
                client_factory=SpotTradingClientFactory(
                    session_factory, credentials, metadata_provider
                ),
                metadata_provider=metadata_provider,
            ),
            commission_reader=SpotCommissionRateReader(session_factory, credentials),
            book_ticker_reader=SpotBookTickerReader(session_factory),
        )
        contexts = FakeVenueContexts(context)
        session_state = TradingSessionState()
        session_state.enable(set())
        preview_handler = PreviewOrderQueryHandler(contexts)
        limit_policy = TradingLimitPolicy(_LIMITS)
        dispatcher = _RoutingDispatcher(
            {
                GetSymbolOrderRulesQuery: GetSymbolOrderRulesQueryHandler(contexts),
                GetCommissionRateQuery: GetCommissionRateQueryHandler(contexts),
                GetExchangeConnectionStatusQuery: GetExchangeConnectionStatusQueryHandler(
                    contexts
                ),
                GetOpenPositionsQuery: GetOpenPositionsQueryHandler(contexts),
                GetOrderNotionalLimitQuery: GetOrderNotionalLimitQueryHandler(
                    limit_policy
                ),
                GetBestBidAskQuery: GetBestBidAskQueryHandler(contexts),
                PreviewOrderQuery: preview_handler,
                ExecuteOrderCommand: ExecuteOrderCommandHandler(
                    single_venue_scopes(context, session_state),
                    preview_handler,
                    limit_policy,
                ),
            }
        )
        ports = fake_venue_ports(
            _SPOT,
            order_submission=OrderSubmissionService(dispatcher, _SPOT),
            account_snapshot=AccountSnapshotService(dispatcher, _SPOT),
            order_entry_terms=OrderEntryTermsService(dispatcher, _SPOT),
        )
        view_model = OrderEntryViewModel(desk_profile_for(_SPOT))
        asked: list[OrderConfirmation] = []

        def answer_yes(confirmation: OrderConfirmation) -> bool:
            asked.append(confirmation)
            return True

        presenter = OrderEntryPresenter(
            view_model, ports, _InlineThreadManager(), answer_yes
        )
        presenter.show_symbol(_SYMBOL)
        assert view_model.context is not None, view_model.message
        presenter.update_last_price(_FAKE_LAST_PRICE)
        yield _SpotPanel(view_model, presenter, asked)


def test_a_confirmed_buy_on_the_panel_moves_the_btc_holding(qtbot) -> None:
    with _spot_panel_on_fake_server() as panel:
        view_model = panel.view_model
        before = view_model.context
        assert before is not None
        assert before.free_base is not None and before.available_quote is not None
        view_model.intents.set_order_type(OrderType.MARKET)
        view_model.intents.set_total(EntrySide.BUY, "500")
        view_model.intents.request_submit(EntrySide.BUY)

        assert not view_model.message_is_error, view_model.message
        assert panel.asked[0].question.startswith("Spend 500.00 USDT to buy BTC")
        after = view_model.context
        assert after is not None and after.free_base is not None
        # `quoteOrderQty`: exactly the total is spent; the fee is charged in
        # BTC on a Spot buy (`spot_account_state.py`), so the holding grows
        # by what 500 USDT buys at 50000, less that fee.
        assert after.available_quote == before.available_quote - 500
        assert before.free_base < after.free_base <= before.free_base + Decimal("0.01")


def test_the_panel_reads_the_app_notional_limit_and_caps_its_maximum(qtbot) -> None:
    with _spot_panel_on_fake_server() as panel:
        context = panel.view_model.context
        assert context is not None
        assert context.notional_limit == _LIMITS.max_notional_per_order
        assert context.available_quote is not None
        assert context.available_quote > _LIMITS.max_notional_per_order

        panel.view_model.intents.set_order_type(OrderType.MARKET)
        figures = panel.view_model.figures(EntrySide.BUY)

        assert figures is not None
        assert figures.max_total == _LIMITS.max_notional_per_order


def test_the_bbo_button_fills_each_side_from_the_venue_book(qtbot) -> None:
    with _spot_panel_on_fake_server() as panel:
        panel.view_model.intents.use_best_price(EntrySide.BUY)
        panel.view_model.intents.use_best_price(EntrySide.SELL)

        assert not panel.view_model.message_is_error, panel.view_model.message
        # The fake's book is one cent either side of its last price.
        assert panel.view_model.entry(EntrySide.BUY).price == Decimal("49999.99")
        assert panel.view_model.entry(EntrySide.SELL).price == Decimal("50000.01")


def test_a_stop_limit_buy_rests_on_the_exchange_until_its_stop(qtbot) -> None:
    with _spot_panel_on_fake_server() as panel:
        view_model = panel.view_model
        before = view_model.context
        assert before is not None
        view_model.intents.set_order_type(OrderType.STOP_LIMIT)
        view_model.intents.set_stop_price(EntrySide.BUY, "51000")
        view_model.intents.set_price(EntrySide.BUY, "51100")
        view_model.intents.set_quantity(EntrySide.BUY, "0.001")
        view_model.intents.request_submit(EntrySide.BUY)

        assert not view_model.message_is_error, view_model.message
        assert "once the price reaches 51,000.00 USDT" in panel.asked[0].question
        after = view_model.context
        assert after is not None
        # Resting, not filled: no BTC bought yet.
        assert after.free_base == before.free_base
