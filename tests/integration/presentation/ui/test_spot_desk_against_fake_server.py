"""`EPIC-033P` stage 3 — the Spot desk in the composed app, with Spot Testnet
enabled, against the fake Binance server: an order typed after Trade → New
order… (F9) runs from the desk's own Buy button to the wire and back.

@details Re-homed from the Dev Board's F9 tests (`EPIC-028S`), which proved
this path through the board's order dialog; the dialog was the desks' order
panel, so the desk is where the path lives now. `create_app()` builds
everything, including the venue registry, the real dispatcher and the real
handlers. Four boundaries are substituted, at configuration:
- the network: `python-binance` points at `run_binance_fake_server()` and
  the venue's key pair comes from the environment;
- the chart's market data, through the same seeded fakes the rest of this
  directory uses;
- the "Place this order?" dialog, a recorded Yes;
- `python-binance`'s `get_loop()`, which hands each worker thread a new event
  loop and never closes it (`BUG-075`). Each module binds the name itself
  (`Client.__init__` reaches it through `base_client` and, via `WebsocketAPI`,
  `ws.reconnecting_websocket`), so every binding (`_GET_LOOP_BINDINGS`) returns
  one loop the fixture owns and closes; `test_no_event_loop_is_left_unclosed`
  fails if one comes back.

Only the "trading on" test seeds the session as enabled directly: the toggle
would also start the venue's user-data websocket, which the fake server does
not speak. The composed path from the toggle through
`EnableTradingCommandHandler` is proven at unit level only (`EPIC-028S` §3).
The unit tests over fakes are `tests/unit/modules/trading/ui/desk/`.
"""

from __future__ import annotations

import asyncio
import gc
import json
import sys
import warnings
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton
from pytestqt.qtbot import QtBot
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen import (
    desk_presenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_commands import (
    new_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_presenter import (
    DeskPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view import (
    DeskView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.spot_desk_screen import (
    SPOT_DESK_ROUTE,
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
from Sagittarius_Elite_Warrior.tests.conftest import real_main_window
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server

_SPOT = TradingVenue.SPOT_TESTNET
_CONFIG_DIR = Path(__file__).resolve().parents[4] / "src" / "config"
#: The fake Spot account's USDT (`fake_exchange/spot_account_state.py`).
_FAKE_USDT = Decimal(100000)
#: Far below the fake's last price for the desk's symbol, so a Limit buy rests
#: open; its notional sits inside the app's per-order limit (`app_config.json`).
_RESTING_PRICE = "30000"
_QUANTITY = "0.001"
_WAIT_MS = 10_000
#: Every `python-binance` module that imports `get_loop` under its own name.
_GET_LOOP_BINDINGS = (
    "binance.base_client.get_loop",
    "binance.async_client.get_loop",
    "binance.ws.reconnecting_websocket.get_loop",
    "binance.ws.streams.get_loop",
    "binance.ws.threaded_stream.get_loop",
    "binance.ws.depthcache.get_loop",
)


@dataclass
class _Desk:
    window: MainWindow
    view: DeskView
    presenter: DeskPresenter
    urls: FakeServerUrls
    scopes: VenueTradingScopes


def _yes(_parent: object) -> ConfirmOrder:
    def confirm(_confirmation: OrderConfirmation) -> bool:
        return True

    return confirm


@dataclass
class _Boot:
    """What booting the app here needs from pytest and this directory."""

    qapp: QApplication
    qtbot: QtBot
    monkeypatch: pytest.MonkeyPatch
    tmp_path: Path
    seeded_history: object
    market_stream: object
    range_coverage: object
    symbol_catalog: object


@pytest.fixture
def boot(
    qapp,
    qtbot,
    monkeypatch,
    tmp_path,
    seeded_history,
    market_stream,
    range_coverage,
    symbol_catalog,
) -> _Boot:
    return _Boot(
        qapp,
        qtbot,
        monkeypatch,
        tmp_path,
        seeded_history,
        market_stream,
        range_coverage,
        symbol_catalog,
    )


@pytest.fixture
def spot_desk(boot: _Boot) -> Iterator[_Desk]:
    with _spot_desk_running(boot) as desk:
        yield desk


@contextmanager
def _spot_desk_running(boot: _Boot) -> Iterator[_Desk]:
    """The real app with Spot Testnet on, its Spot desk open."""
    qapp, monkeypatch, tmp_path = boot.qapp, boot.monkeypatch, boot.tmp_path
    seeded_history, market_stream = boot.seeded_history, boot.market_stream
    range_coverage, symbol_catalog = boot.range_coverage, boot.symbol_catalog
    monkeypatch.setenv(SPOT_ENV_API_KEY, "fake-key")
    monkeypatch.setenv(SPOT_ENV_API_SECRET, "fake-secret")
    # Read when the presenter is built (`deps.confirm or ...`), so the
    # module's own name is the one to replace.
    monkeypatch.setattr(desk_presenter, "confirm_with_message_box", _yes)
    user_json = tmp_path / "user_config.json"
    user_json.write_text(json.dumps({}))
    config = ConfigManager()
    config.load_json(str(_CONFIG_DIR / "app_config.json"))
    config.load_json(str(user_json), writable=True)
    config.load_dict({"exchange.trading_venues": [_SPOT.value]})
    loop = asyncio.new_event_loop()
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        ExitStack() as owned_loop,
    ):
        for binding in _GET_LOOP_BINDINGS:
            owned_loop.enter_context(patch(binding, lambda: loop))
        engine = create_app(config)
        container = engine.context.container
        container.singleton(IHistoricalKlines, lambda _c: seeded_history)
        container.singleton(IMarketStream, lambda _c: market_stream)
        container.singleton(IRangeCoverage, lambda _c: range_coverage)
        container.singleton(ISymbolCatalog, lambda _c: symbol_catalog)
        engine.boot()
        window = real_main_window(engine)
        window.show()
        # Not handed to `qtbot.addWidget`: the `finally` below closes and
        # deletes the window itself, and qtbot closing it again afterwards
        # finds the C++ object gone while a caller still holds the desk.
        window.switch_screen(SPOT_DESK_ROUTE)
        qapp.processEvents()
        presenter = window.presenters[SPOT_DESK_ROUTE]
        view = window.hosts[SPOT_DESK_ROUTE].view
        assert isinstance(presenter, DeskPresenter)
        assert isinstance(view, DeskView)
        try:
            yield _Desk(
                window, view, presenter, urls, container.resolve(VenueTradingScopes)
            )
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


def _new_order(desk: _Desk) -> None:
    """Trade → New order… (F9), the window's own action."""
    action = desk.window.findChild(QAction, f"action::{new_order_id(_SPOT)}")
    assert action is not None
    action.trigger()


def _type_resting_limit_buy(desk: _Desk, qtbot) -> None:
    vm = desk.presenter.orders
    qtbot.waitUntil(lambda: vm.context is not None, timeout=_WAIT_MS)
    vm.set_order_type(OrderType.LIMIT)
    vm.set_price(EntrySide.BUY, _RESTING_PRICE)
    vm.set_quantity(EntrySide.BUY, _QUANTITY)


def _buy(desk: _Desk, qtbot) -> None:
    qtbot.mouseClick(
        desk.view.findChild(QPushButton, "btnSubmitBuy"), Qt.MouseButton.LeftButton
    )


def _order_posts(urls: FakeServerUrls) -> list[tuple[str, str]]:
    """Live order placements only: not `/order/test` (validate-only) nor
    `/orderList`."""
    return [r for r in urls.requests if r == ("POST", "/api/v3/order")]


def test_f9_focuses_the_spot_entry_read_from_the_venue(spot_desk, qtbot) -> None:
    vm = spot_desk.presenter.orders
    assert vm.profile.venue is _SPOT
    qtbot.waitUntil(lambda: vm.context is not None, timeout=_WAIT_MS)
    spot_desk.view.activateWindow()

    _new_order(spot_desk)

    price = spot_desk.view.findChild(QLineEdit, "txtPriceBuy")
    qtbot.waitUntil(lambda: QApplication.focusWidget() is price, timeout=_WAIT_MS)
    assert vm.context.available_quote == _FAKE_USDT
    assert _order_posts(spot_desk.urls) == []


def test_a_buy_while_trading_is_off_is_refused_in_words_and_never_sent(
    spot_desk, qtbot
) -> None:
    """The real handler's gate answers, and nothing reaches the exchange."""
    _new_order(spot_desk)
    _type_resting_limit_buy(spot_desk, qtbot)
    vm = spot_desk.presenter.orders
    refusal = format_execute_order_block_reason(
        ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
    )

    _buy(spot_desk, qtbot)

    qtbot.waitUntil(lambda: refusal in vm.message, timeout=_WAIT_MS)
    assert vm.message_is_error
    assert _order_posts(spot_desk.urls) == []


def test_a_resting_limit_placed_on_the_desk_reaches_the_venue_and_open_orders(
    spot_desk, qtbot
) -> None:
    spot_desk.scopes.get(_SPOT).session_state.enable(
        set(), spot_baseline_holdings={"USDT": _FAKE_USDT}
    )
    _new_order(spot_desk)
    _type_resting_limit_buy(spot_desk, qtbot)

    _buy(spot_desk, qtbot)

    qtbot.waitUntil(lambda: len(_order_posts(spot_desk.urls)) == 1, timeout=_WAIT_MS)
    rows = spot_desk.view.account_tabs.open_orders_panel.table.model()
    qtbot.waitUntil(lambda: rows.rowCount() == 1, timeout=_WAIT_MS)
    cells = [rows.index(0, column).data() for column in range(rows.columnCount())]
    assert spot_desk.presenter.desk.symbol in cells
    assert "BUY" in cells
    assert "LIMIT" in cells
    assert "NEW" in cells  # resting on the exchange, not a validate-only echo


def test_no_event_loop_is_left_unclosed(boot: _Boot, qtbot) -> None:
    """The PR 310 review — `python-binance` gives each worker thread an event
    loop and never closes it (`BUG-075`). Patching one of its `get_loop`
    bindings left the leak in place; an orphaned loop is collected later and
    fails whichever test is running. Booting, reading the desk's order entry
    and shutting down leaves no unclosed loop behind."""
    gc.collect()  # what earlier tests left is not this file's
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        with _spot_desk_running(boot) as desk:
            _new_order(desk)
            vm = desk.presenter.orders
            qtbot.waitUntil(lambda: vm.context is not None, timeout=_WAIT_MS)
        gc.collect()

    leaks = [w for w in caught if "unclosed event loop" in str(w.message)]
    assert leaks == []
