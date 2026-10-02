"""`EPIC-028S` — the Dev Board's F9 dialog in the composed app, with Spot
Testnet enabled, against the fake Binance server.

@details The PR 309 review found that no test exercised F9 with a venue on in
the real app any more: `test_dev_board_order_dialog.py` boots with trading off
and can only assert the notice. Here `create_app()` builds everything,
including the venue registry, the real dispatcher and the real handlers. Three
boundaries are substituted, at configuration:
- the network: `python-binance` points at `run_binance_fake_server()` and
  the venue's key pair comes from the environment;
- the chart's market data, through the same seeded fakes the rest of this
  directory uses;
- the "Place this order?" dialog, a recorded Yes;
- `python-binance`'s `get_loop()`, which hands each worker thread a new event
  loop and never closes it (`BUG-075`): here every `Client` gets one loop the
  fixture owns and closes, so no orphaned loop is collected in a later test.

A click in F9 therefore runs through the composed panel and the real
`ExecuteOrderCommandHandler` to the wire and back. Only the "trading on" test
seeds the session as enabled directly: the toggle would also start the
venue's user-data websocket, which the fake server does not speak.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QPushButton
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_range_coverage import (
    IRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard import (
    dashboard_presenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dev_board_panel import (
    MANUAL_ORDER_DIALOG,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_confirmation import (
    ConfirmOrder,
    OrderConfirmation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.sidebar import Sidebar
from Sagittarius_Elite_Warrior.tests.conftest import real_screen_registry
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server

_SPOT = TradingVenue.SPOT_TESTNET
_CONFIG_DIR = Path(__file__).resolve().parents[4] / "src" / "config"
#: The fake Spot account's USDT (`fake_exchange/spot_account_state.py`).
_FAKE_USDT = Decimal(100000)
#: Far below the fake's last price for the board's symbol, so a Limit buy rests
#: open; its notional sits inside the app's per-order limit (`app_config.json`).
_RESTING_PRICE = "30000"
_QUANTITY = "0.001"
_WAIT_MS = 10_000


@dataclass
class _Board:
    window: MainWindow
    presenter: DashboardPresenter
    urls: FakeServerUrls
    scopes: VenueTradingScopes


def _yes(_parent: object) -> ConfirmOrder:
    def confirm(_confirmation: OrderConfirmation) -> bool:
        return True

    return confirm


@pytest.fixture
def spot_board(
    qapp,
    qtbot,
    monkeypatch,
    tmp_path,
    seeded_history,
    market_stream,
    range_coverage,
    symbol_catalog,
) -> Iterator[_Board]:
    """The real app with Spot Testnet on, its Dev Board open."""
    monkeypatch.setenv(SPOT_ENV_API_KEY, "fake-key")
    monkeypatch.setenv(SPOT_ENV_API_SECRET, "fake-secret")
    monkeypatch.setattr(dashboard_presenter, "confirm_with_message_box", _yes)
    user_json = tmp_path / "user_config.json"
    user_json.write_text(json.dumps({}))
    config = ConfigManager()
    config.load_json(str(_CONFIG_DIR / "app_config.json"))
    config.load_json(str(user_json), writable=True)
    config.load_dict(
        {
            "exchange.trading_venues": [_SPOT.value],
            # The chart's own Start Live is not what this file tests.
            "DEV_BOARD_AUTOSTART_ENABLED": False,
        }
    )
    loop = asyncio.new_event_loop()
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch("binance.base_client.get_loop", lambda: loop),
    ):
        engine = create_app(config)
        container = engine.context.container
        container.singleton(IHistoricalKlines, lambda _c: seeded_history)
        container.singleton(IMarketStream, lambda _c: market_stream)
        container.singleton(IRangeCoverage, lambda _c: range_coverage)
        container.singleton(ISymbolCatalog, lambda _c: symbol_catalog)
        engine.boot()
        window = MainWindow(
            engine, real_screen_registry(container), sidebar_factory=Sidebar
        )
        window.show()
        qtbot.addWidget(window)
        window._sidebar._nav_buttons["dashboard"].click()
        qapp.processEvents()
        presenter = window._router._registry["dashboard"]["presenter_instance"]
        try:
            yield _Board(window, presenter, urls, container.resolve(VenueTradingScopes))
        finally:
            threads = container.resolve(IThreadManager)
            threads.shutdown(wait=True)
            assert threads.stats().in_flight == 0
            window.close()
            window.deleteLater()
            engine.stop()
            loop.close()
            app = QApplication.instance()
            if app is not None:
                app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                app.processEvents()


def _open_f9(board: _Board):
    view = board.window._router._registry["dashboard"]["view_instance"]
    view._manual_order_action.trigger()
    return view._surface.show_modal(MANUAL_ORDER_DIALOG)


def _type_resting_limit_buy(board: _Board, qtbot) -> None:
    entry = board.presenter._order_entry
    assert entry is not None
    vm = entry.view_model
    qtbot.waitUntil(lambda: vm.context is not None, timeout=_WAIT_MS)
    vm.set_order_type(OrderType.LIMIT)
    vm.set_price(EntrySide.BUY, _RESTING_PRICE)
    vm.set_quantity(EntrySide.BUY, _QUANTITY)


def _order_posts(urls: FakeServerUrls) -> list[tuple[str, str]]:
    return [
        r for r in urls.requests if r[0] == "POST" and r[1].startswith("/api/v3/order")
    ]


def test_f9_holds_the_spot_panel_read_from_the_venue(spot_board, qtbot) -> None:
    dialog = _open_f9(spot_board)
    entry = spot_board.presenter._order_entry

    assert entry is not None
    assert entry.view_model.profile.venue is _SPOT
    assert dialog.findChild(QPushButton, "btnSubmitBuy") is not None
    qtbot.waitUntil(lambda: entry.view_model.context is not None, timeout=_WAIT_MS)
    assert entry.view_model.context.available_quote == _FAKE_USDT


def test_a_buy_while_trading_is_off_is_refused_in_words_and_never_sent(
    spot_board, qtbot
) -> None:
    """The deleted manual-order click test's subject, with a venue on: the
    real handler's gate answers, and nothing reaches the exchange."""
    dialog = _open_f9(spot_board)
    _type_resting_limit_buy(spot_board, qtbot)
    vm = spot_board.presenter._order_entry.view_model
    refusal = format_execute_order_block_reason(
        ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
    )

    qtbot.mouseClick(
        dialog.findChild(QPushButton, "btnSubmitBuy"), Qt.MouseButton.LeftButton
    )

    qtbot.waitUntil(lambda: refusal in vm.message, timeout=_WAIT_MS)
    assert vm.message_is_error
    assert _order_posts(spot_board.urls) == []


def test_a_resting_limit_placed_in_f9_reaches_the_venue_and_open_orders(
    spot_board, qtbot
) -> None:
    spot_board.scopes.get(_SPOT).session_state.enable(
        set(), spot_baseline_holdings={"USDT": _FAKE_USDT}
    )
    dialog = _open_f9(spot_board)
    _type_resting_limit_buy(spot_board, qtbot)
    view = spot_board.window._router._registry["dashboard"]["view_instance"]

    qtbot.mouseClick(
        dialog.findChild(QPushButton, "btnSubmitBuy"), Qt.MouseButton.LeftButton
    )

    qtbot.waitUntil(lambda: len(_order_posts(spot_board.urls)) == 1, timeout=_WAIT_MS)
    rows = view._open_orders_panel.table.model()
    qtbot.waitUntil(lambda: rows.rowCount() == 1, timeout=_WAIT_MS)
    cells = [rows.index(0, column).data() for column in range(rows.columnCount())]
    assert cells[:3] == [spot_board.presenter._active_symbol, "BUY", "LIMIT"]
