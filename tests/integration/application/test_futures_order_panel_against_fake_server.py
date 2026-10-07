"""`EPIC-028I` — the Futures order panel against the fake exchange: its
leverage chip changes the exchange's leverage and reads it back, and a
market long placed with TP/SL on is protected by a take-profit and a
stop-loss once its fill is reported.

@details Every query and command goes to its real handler, the Futures
readers and client and `python-binance`, on the fake exchange. The fill is
published on the bus as the user-data stream would (the stream itself does
not run here); `ProtectiveOrderFollower` hears it through the real
`OrderFeed` and places both orders through the real submission path. The
dialog is a recorded "Yes" and the worker pool runs inline.
"""

from __future__ import annotations

import concurrent.futures
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_control import (
    FuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_account_reader import (
    FuturesAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_book_ticker_reader import (
    FuturesBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_commission_rate_reader import (
    FuturesCommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_mark_price_reader import (
    FuturesMarkPriceReader,
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
from Sagittarius_Elite_Warrior.src.modules.trading.application.account.account_snapshot_service import (
    AccountSnapshotService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_leverage import (
    ChangeLeverageCommand,
    ChangeLeverageCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.change_margin_type import (
    ChangeMarginTypeCommand,
    ChangeMarginTypeCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.account_control.futures_settings_service import (
    FuturesSettingsService,
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
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_futures_symbol_setting import (
    GetFuturesSymbolSettingQuery,
    GetFuturesSymbolSettingQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_leverage_brackets import (
    GetLeverageBracketsQuery,
    GetLeverageBracketsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_mark_price import (
    GetMarkPriceQuery,
    GetMarkPriceQueryHandler,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_presenter import (
    OrderEntryPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.protective_order_follower import (
    ProtectiveOrderFollower,
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
from binance_fake_server import run_binance_fake_server

_FUTURES = TradingVenue.FUTURES_TESTNET
_SYMBOL = "BTCUSDT"
#: The fake exchange's `BTCUSDT` last price.
_LAST = Decimal(50000)
_LIMITS = TradingLimits(
    max_orders_per_session=1,
    max_notional_per_order=Decimal(100000),
    max_positions_per_symbol=1,
    min_order_interval=timedelta(minutes=10),
)


class _Credentials(IExchangeCredentialsProvider):
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise AssertionError("not used by this test")


class _RoutingDispatcher(ICommandDispatcher):
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


def _dispatcher() -> tuple[_RoutingDispatcher, FuturesTradingClientFactory]:
    sessions = FuturesSessionFactory()
    credentials = _Credentials()
    metadata = FuturesMetadataProvider(sessions, InMemorySymbolOrderMetadataCache())
    clients = FuturesTradingClientFactory(sessions, credentials, metadata)
    context = replace(
        venue_context(
            _FUTURES,
            account_reader=FuturesAccountReader(sessions, credentials),
            client_factory=clients,
            metadata_provider=metadata,
            account_control=FuturesAccountControl(sessions, credentials),
        ),
        commission_reader=FuturesCommissionRateReader(sessions, credentials),
        book_ticker_reader=FuturesBookTickerReader(sessions),
        mark_price_reader=FuturesMarkPriceReader(sessions),
    )
    contexts = FakeVenueContexts(context)
    state = TradingSessionState()
    state.enable(set())
    scopes = single_venue_scopes(context, state)
    preview = PreviewOrderQueryHandler(contexts)
    policy = TradingLimitPolicy(_LIMITS)
    return (
        _RoutingDispatcher(
            {
                GetSymbolOrderRulesQuery: GetSymbolOrderRulesQueryHandler(contexts),
                GetCommissionRateQuery: GetCommissionRateQueryHandler(contexts),
                GetExchangeConnectionStatusQuery: GetExchangeConnectionStatusQueryHandler(
                    contexts
                ),
                GetOpenPositionsQuery: GetOpenPositionsQueryHandler(contexts),
                GetOrderNotionalLimitQuery: GetOrderNotionalLimitQueryHandler(policy),
                GetBestBidAskQuery: GetBestBidAskQueryHandler(contexts),
                GetFuturesSymbolSettingQuery: GetFuturesSymbolSettingQueryHandler(
                    contexts
                ),
                GetLeverageBracketsQuery: GetLeverageBracketsQueryHandler(contexts),
                GetMarkPriceQuery: GetMarkPriceQueryHandler(contexts),
                PreviewOrderQuery: preview,
                ExecuteOrderCommand: ExecuteOrderCommandHandler(
                    scopes, preview, policy
                ),
                ChangeLeverageCommand: ChangeLeverageCommandHandler(scopes),
                ChangeMarginTypeCommand: ChangeMarginTypeCommandHandler(scopes),
            }
        ),
        clients,
    )


def test_a_market_long_with_tp_sl_is_protected_once_its_fill_is_reported(
    qapp,
) -> None:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        dispatcher, clients = _dispatcher()
        submission = OrderSubmissionService(dispatcher, _FUTURES)
        ports = fake_venue_ports(
            _FUTURES,
            order_submission=submission,
            account_snapshot=AccountSnapshotService(dispatcher, _FUTURES),
            order_entry_terms=OrderEntryTermsService(dispatcher, _FUTURES),
            futures_settings=FuturesSettingsService(dispatcher, _FUTURES),
        )
        threads = _InlineThreadManager()
        vm = OrderEntryViewModel(desk_profile_for(_FUTURES))
        presenter = OrderEntryPresenter(
            vm, ports, threads, lambda _c: True, RecordingNotifier()
        )
        bus = MemoryEventBus()
        reports: list[tuple[str, bool]] = []
        # The test owns the feed, as the desk does (`parent=`); a bus
        # subscription keeps no subscriber alive (Engine `BUG-019`).
        feed = OrderFeed(bus, _FUTURES)
        follower = ProtectiveOrderFollower(
            submission,
            feed,
            threads,
            lambda text, failed: reports.append((text, failed)),
            RecordingNotifier(),
            _FUTURES,
        )
        presenter.entryPlaced.connect(lambda placed: follower.expect(*placed))
        presenter.show_symbol(_SYMBOL)
        vm.presenter_side().set_last_price(_LAST)

        vm.options.request_leverage(20)
        setting = vm.options.setting
        assert setting is not None and setting.leverage == 20, vm.message

        vm.intents.set_order_type(OrderType.MARKET)
        vm.intents.set_quantity(EntrySide.BUY, "0.01")
        vm.options.set_tp_sl_enabled(True)
        vm.options.set_take_profit(EntrySide.BUY, "52000")
        vm.options.set_stop_loss(EntrySide.BUY, "48000")
        vm.intents.request_submit(EntrySide.BUY)
        (entry_id,) = follower.waiting
        client = clients.create(OrderSubmissionMode.VALIDATE_ONLY)
        assert client.get_open_orders(_SYMBOL) == []

        entry = Order(
            client_order_id=entry_id,  # type: ignore[arg-type]
            symbol=_SYMBOL,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.01"),
            status=OrderStatus.FILLED,
        )
        bus.emit(
            OrderFilledEvent(
                order=entry,
                fill_price=_LAST,
                fill_quantity=Decimal("0.01"),
                venue=_FUTURES,
            )
        )
        qapp.processEvents()

        assert reports == [
            ("Take-profit placed at 52000. Stop-loss placed at 48000.", False)
        ]
        resting = client.get_open_orders(_SYMBOL)
        assert sorted(o.order_type.value for o in resting) == [
            "stop_market",
            "take_profit_market",
        ]
        assert all(o.side is OrderSide.SELL and o.reduce_only for o in resting)
        assert {o.stop_price for o in resting} == {Decimal(52000), Decimal(48000)}
