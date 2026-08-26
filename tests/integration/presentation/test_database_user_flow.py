"""Deterministic Database screen (Storage Vault) user-flow integration tests."""

from __future__ import annotations

import os
import time
from unittest.mock import patch

import pytest
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _FakeExchangeClient:
    """A hand-written `IExchangeClient`, deliberately not a `Mock(spec=...)`.

    @par Why not a Mock
    `spec=` constrains method *names* only, never return types, so any path
    this fixture has not explicitly configured hands a bare `Mock` to real
    production code, which then blows up on `len()` or iteration deep inside
    a handler. This has bitten twice, both under parallel runs, both in this
    file, three days apart:

      * 2026-08-23 — `ListAvailableSymbolsQuery failed: object of type
        'Mock' has no len()` (recorded in `BUG-030`)
      * 2026-08-26 — `SyncMarketDataCommand failed: 'Mock' object is not
        iterable` (`BUG-062`)

    Each was patched by configuring one more method on the Mock, which fixes
    that sighting and leaves the class open. A real class cannot produce a
    bare `Mock` at all: an unimplemented method is an `AttributeError` naming
    itself, at the call site, every run.

    @par `stream_historical_klines` returns a FRESH iterator per call
    The Mock it replaces used `return_value = iter(())` — a one-shot
    iterator, so every call after the first returned the *same*, already
    exhausted object. Empty either way here, but a test that ever syncs
    twice would silently get nothing the second time and read as passing.
    """

    #: Kept a plain attribute so a test can widen it without touching a Mock.
    available_symbols: list[str]

    def __init__(self) -> None:
        self.available_symbols = ["BTCUSDT", "ETHUSDT"]

    def get_historical_klines(self, *args: object, **kwargs: object) -> list:
        # The 0.3s the Mock's side_effect slept for: these tests need the
        # fetch to still be in flight when they assert on the busy state.
        time.sleep(0.3)
        return []

    def stream_historical_klines(self, *args: object, **kwargs: object):
        return iter(())

    def get_available_symbols(self) -> list[str]:
        return list(self.available_symbols)


@pytest.fixture
def database_app_context(qapp, qtbot, monkeypatch, request):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    config_manager = ConfigManager()
    bot_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )
    config_manager.load_json(os.path.join(bot_root, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(bot_root, "src", "config", "user_config.json")
    )
    app = create_app(config_manager)

    with (
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        app.boot()
        mock_client = _FakeExchangeClient()
        app.context.container.singleton(IExchangeClient, mock_client)

        view = DataManagementView()
        qtbot.addWidget(view)
        presenter = DataManagementPresenter(view, app.context.container)
        view.show()
        qapp.processEvents()

        yield view, presenter, mock_client

        presenter._thread_manager.shutdown(wait=True)
        view.close()
        view.deleteLater()
        app.stop()


def test_database_cancel_button_cancels_active_sync_flow(
    qapp, qtbot, database_app_context
):
    """EPIC-005E: DataManagementView is QtWidgets now (was QmlHostView) —
    `btnCancelSync` is a real QPushButton (`view._btn_cancel_sync`), not a
    QML item reached through `qml_item()`/`quick_widget.rootObject()`."""
    view, presenter, _ = database_app_context
    cancel_btn = view._btn_cancel_sync
    view_model = presenter._view_model

    # Start single sync
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "1m"
    view_model.requestSync()
    qapp.processEvents()

    # Wait until in SYNCING state and progress is visible
    qtbot.waitUntil(lambda: presenter.fsm.current_state == UIMode.SYNCING, timeout=2000)
    assert cancel_btn.isVisible() is True
    assert cancel_btn.isEnabled() is True

    # Click Cancel
    cancel_btn.click()
    qapp.processEvents()

    # FSM transitions through CANCELLING then back to IDLE
    qtbot.waitUntil(lambda: presenter.fsm.current_state == UIMode.IDLE, timeout=5000)
    assert view_model.progressVisible is False


def test_the_fake_client_still_covers_every_method_the_port_declares():
    """The one thing a hand-written fake gives up versus `Mock(spec=...)`:
    it does not follow the port automatically. A method added to
    `IExchangeClient` would reach this fixture as an `AttributeError` at
    whatever call site happened to hit it first — loud, but late and in a
    confusing place. Asserted here instead, where the message says what to do.

    The reverse direction matters too: a method the fake declares and the
    port no longer has is dead weight that outlives the port, so both sets
    are compared, not just one inclusion.
    """
    port_methods = {
        name
        for name in vars(IExchangeClient)
        if callable(getattr(IExchangeClient, name)) and not name.startswith("_")
    }
    fake_methods = {
        name
        for name in vars(_FakeExchangeClient)
        if callable(getattr(_FakeExchangeClient, name)) and not name.startswith("_")
    }

    assert port_methods == fake_methods, (
        "_FakeExchangeClient has drifted from IExchangeClient — "
        f"only on the port: {sorted(port_methods - fake_methods)}; "
        f"only on the fake: {sorted(fake_methods - port_methods)}"
    )


def test_streaming_twice_yields_a_fresh_iterator_each_time():
    """Pins the defect the replaced Mock carried: `return_value = iter(())`
    handed back the *same* exhausted iterator on every call after the first.
    Both calls are empty here either way — the point is that the second one
    is empty because there is nothing to stream, not because the first call
    consumed the object."""
    client = _FakeExchangeClient()

    first = client.stream_historical_klines()
    second = client.stream_historical_klines()

    assert first is not second
