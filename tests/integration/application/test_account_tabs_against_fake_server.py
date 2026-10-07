"""`EPIC-028J` — a Futures desk opened after orders were placed elsewhere
lists them, shows them in its order history, and cancels them all, against
the fake exchange.

@details What the unit tests cannot show: that the tabs' reads are the
venue's real open orders and history (`GetOpenOrdersQuery`,
`GetOrderHistoryQuery`, the Algo Order API's lists included), and that
"Cancel all" reaches the wire through `CancelOrderCommandHandler`,
`FuturesTradingClient` and `python-binance`. Both orders are placed straight
on the fake, as Binance's own UI would: the app never sent them. The
dispatcher routes each query and command to its real handler; the
container's wiring is `test_composition_root.py`'s. The dialogs are a
recorded "Yes" and the worker pool runs inline.
"""

from __future__ import annotations

import concurrent.futures
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

from binance.client import Client
from PySide6.QtGui import QAction
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_reader import (
    FuturesHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_metadata_provider import (
    FuturesMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.account_activity_service import (
    AccountActivityService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.account_snapshot_service import (
    AccountSnapshotService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order import (
    CancelOrderCommand,
    CancelOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.order_submission_service import (
    OrderSubmissionService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
    GetExchangeConnectionStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_orders import (
    GetOpenOrdersQuery,
    GetOpenOrdersQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
    GetOpenPositionsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_history import (
    GetOrderHistoryQuery,
    GetOrderHistoryQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_trade_history import (
    GetTradeHistoryQuery,
    GetTradeHistoryQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_real_money_consent import (
    FakeRealMoneyConsent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tab_confirmations import (
    AccountTabConfirmations,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_panel import (
    AccountTabsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_presenter import (
    AccountTabsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_view import (
    HistoryKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    HeldTab,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server

_FUTURES = TradingVenue.FUTURES_TESTNET


class _Credentials(IExchangeCredentialsProvider):
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used by this test")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


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


def _place_elsewhere(urls: FakeServerUrls) -> None:
    """A resting limit order and a conditional order, as Binance's UI
    would place them."""
    status, _ = urls.futures_book.place(
        {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "quantity": "0.01",
            "price": "40000",
            "timeInForce": "GTC",
            "newClientOrderId": "web_limit_in_binance_ui",
        }
    )
    assert status == 200
    status, _ = urls.futures_book.algo.place(
        {
            "algoType": "CONDITIONAL",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "STOP_MARKET",
            "quantity": "0.01",
            "triggerPrice": "70000",
            "clientAlgoId": "web_stop_in_binance_ui",
        }
    )
    assert status == 200


def _desk(qtbot) -> AccountTabsPanel:
    sessions = FuturesSessionFactory()
    metadata = FuturesMetadataProvider(sessions, InMemorySymbolOrderMetadataCache())
    context = replace(
        venue_context(
            _FUTURES,
            account_reader=FuturesAccountReader(sessions, _Credentials()),
            client_factory=FuturesTradingClientFactory(
                sessions, _Credentials(), metadata
            ),
            metadata_provider=metadata,
        ),
        history_reader=FuturesHistoryReader(
            sessions, _Credentials(), lambda: datetime.now(UTC)
        ),
    )
    contexts = FakeVenueContexts(context)
    state = TradingSessionState()
    state.enable(set())
    dispatcher = _RoutingDispatcher(
        {
            GetOpenOrdersQuery: GetOpenOrdersQueryHandler(contexts),
            GetOpenPositionsQuery: GetOpenPositionsQueryHandler(contexts),
            GetExchangeConnectionStatusQuery: GetExchangeConnectionStatusQueryHandler(
                contexts
            ),
            GetOrderHistoryQuery: GetOrderHistoryQueryHandler(contexts),
            GetTradeHistoryQuery: GetTradeHistoryQueryHandler(contexts),
            CancelOrderCommand: CancelOrderCommandHandler(
                single_venue_scopes(context, state)
            ),
        }
    )
    panel = AccountTabsPanel(
        HeldTab.POSITIONS,
        AccountTabConfirmations(cancel_all=lambda _rows: True),
    )
    qtbot.addWidget(panel)
    presenter = AccountTabsPresenter(
        panel,
        fake_venue_ports(
            _FUTURES,
            order_submission=OrderSubmissionService(dispatcher, _FUTURES),
            account_snapshot=AccountSnapshotService(dispatcher, _FUTURES),
            account_activity=AccountActivityService(dispatcher, _FUTURES),
        ),
        OrderFeed(MemoryEventBus(), _FUTURES, parent=panel),
        _InlineThreadManager(),
        RecordingNotifier(),
        FakeRealMoneyConsent(),
    )
    presenter.show_symbol("BTCUSDT")
    return panel


def _open_order_ids(panel: AccountTabsPanel) -> list[str]:
    model = panel.open_orders_panel.table.model().sourceModel()
    return sorted(row.client_order_id for row in model.rows)


def test_a_desk_opened_later_lists_and_cancels_orders_placed_elsewhere(qtbot) -> None:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        _place_elsewhere(urls)
        panel = _desk(qtbot)

        assert _open_order_ids(panel) == [
            "web_limit_in_binance_ui",
            "web_stop_in_binance_ui",
        ]
        history = panel.history_panel(HistoryKind.ORDERS).table.model().sourceModel()
        assert {row.symbol for row in history.rows} == {"BTCUSDT"}
        assert len(history.rows) == 2

        panel.findChild(QAction, "actCancelAllOrders").trigger()

        assert _open_order_ids(panel) == []
        cancels = [path for method, path in urls.requests if method == "DELETE"]
        assert "/fapi/v1/order" in cancels
        assert "/fapi/v1/algoOrder" in cancels
