"""`EPIC-033I` — the real app with Futures and Spot Testnet enabled, against
the fake Binance server, the Trade mode open with Spot chosen: shared by the
mode's order-path tests (`test_trade_mode_against_fake_server.py`) and its
conformance and pictures with both venues built
(`test_trade_mode_conformance.py`).

Four boundaries are substituted, at configuration (see the order-path
file's docstring for each): the network, the chart's market data, the
"Place this order?" dialog (a recorded Yes) and `python-binance`'s
`get_loop()` (`BUG-075`).
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from PySide6.QtCore import QEvent
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen import (
    desk_presenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_presenter import (
    DeskPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_view import (
    DeskView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_confirmation import (
    ConfirmOrder,
    OrderConfirmation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_commands import (
    NEW_ORDER,
    venue_choice_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_presenter import (
    TradePresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_view import (
    TradeView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.main_window import MainWindow
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    FUTURES_ENV_API_KEY,
    FUTURES_ENV_API_SECRET,
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

SPOT = TradingVenue.SPOT_TESTNET
FUTURES = TradingVenue.FUTURES_TESTNET
_CONFIG_DIR = Path(__file__).resolve().parents[4] / "src" / "config"
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
class TradeDesk:
    """The Trade mode with Spot chosen: its Spot page and desk."""

    window: MainWindow
    trade: TradePresenter
    view: DeskView
    presenter: DeskPresenter
    urls: FakeServerUrls
    scopes: VenueTradingScopes


def _yes(_parent: object) -> ConfirmOrder:
    def confirm(_confirmation: OrderConfirmation) -> bool:
        return True

    return confirm


@dataclass
class Boot:
    """What booting the app here needs from pytest and this directory."""

    qapp: QApplication
    qtbot: QtBot
    monkeypatch: pytest.MonkeyPatch
    tmp_path: Path
    seeded_history: object
    market_stream: object
    range_coverage: object
    symbol_catalog: object

    @classmethod
    def from_request(cls, request: pytest.FixtureRequest) -> Boot:
        """This directory's fixtures, as a test's `trade_boot` asks for them."""
        values = [request.getfixturevalue(name) for name in _BOOT_FIXTURES]
        return cls(*values)


#: `Boot`'s fields, in order: the fixtures of pytest, pytest-qt and this
#: directory's `conftest.py` it is made of.
_BOOT_FIXTURES = (
    "qapp",
    "qtbot",
    "monkeypatch",
    "tmp_path",
    "seeded_history",
    "market_stream",
    "range_coverage",
    "symbol_catalog",
)


@contextmanager
def trade_mode_running(boot: Boot) -> Iterator[TradeDesk]:
    """The real app with Futures and Spot Testnet on, the Trade mode open
    with Spot chosen on its toolbar."""
    qapp, monkeypatch, tmp_path = boot.qapp, boot.monkeypatch, boot.tmp_path
    seeded_history, market_stream = boot.seeded_history, boot.market_stream
    range_coverage, symbol_catalog = boot.range_coverage, boot.symbol_catalog
    for key, secret in (
        (SPOT_ENV_API_KEY, SPOT_ENV_API_SECRET),
        (FUTURES_ENV_API_KEY, FUTURES_ENV_API_SECRET),
    ):
        monkeypatch.setenv(key, "fake-key")
        monkeypatch.setenv(secret, "fake-secret")
    # Read when the presenter is built (`deps.confirm or ...`), so the
    # module's own name is the one to replace.
    monkeypatch.setattr(desk_presenter, "confirm_with_message_box", _yes)
    user_json = tmp_path / "user_config.json"
    user_json.write_text(json.dumps({}))
    config = ConfigManager()
    config.load_json(str(_CONFIG_DIR / "app_config.json"))
    config.load_json(str(user_json), writable=True)
    config.load_dict({"exchange.trading_venues": [FUTURES.value, SPOT.value]})
    loop = asyncio.new_event_loop()
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
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
        window.switch_screen(TRADE_ROUTE)
        choose(window, SPOT)
        qapp.processEvents()
        trade = window.presenters[TRADE_ROUTE]
        mode_view = window.hosts[TRADE_ROUTE].view
        assert isinstance(trade, TradePresenter)
        assert isinstance(mode_view, TradeView)
        assert mode_view.shown_venue is SPOT
        try:
            yield TradeDesk(
                window,
                trade,
                mode_view.venue_page(SPOT),
                trade.desks[SPOT],
                urls,
                container.resolve(VenueTradingScopes),
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


def action(window: MainWindow, command_id: str) -> QAction:
    action = window.findChild(QAction, f"action::{command_id}")
    assert action is not None, command_id
    return action


def choose(window: MainWindow, venue: TradingVenue) -> None:
    """Trade → Venue › `venue`, the window's own action."""
    action(window, venue_choice_id(venue)).trigger()


def new_order(desk: TradeDesk) -> None:
    """Trade → New order… (F9), the window's own action."""
    action(desk.window, NEW_ORDER).trigger()
