"""`EPIC-010H` — saving Settings actually takes effect.

@details The three-tier order this settles:

    ui_state  >  user_config DEFAULT_*  >  module constants

A remembered value outranks the Settings default. That is the right order —
what the user just did on a screen should beat what they declared once in
Settings — but it has a mandatory consequence: changing the default has to drop
the remembered value it now loses to. Without that the user edits Settings,
presses Save, and nothing appears to happen.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_presenter import (
    SettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view import (
    SettingsView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_config import IConfig

_BACKTEST = StateScope(key="backtest")

#: A remembered Backtest slice: two keys Settings owns, and three it does not.
_REMEMBERED = {
    "symbol": "SOLUSDT",
    "timeframe": "15m",
    "long_leverage": 3.0,
    "commission": "0.05",
    "timezone": "UTC",
}


@pytest.fixture
def config():
    c = Mock()
    c.get_all.return_value = {
        "API_KEY": "k",
        "API_SECRET": "s",
        "DEFAULT_SYMBOLS": ["BTCUSDT"],
        "DEFAULT_INTERVAL": "1m",
        "DEFAULT_SYNC_DAYS": 30,
    }
    c.get.side_effect = lambda key, default=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )
    return c


@pytest.fixture
def store():
    s = InMemoryStateStore()
    s.write(_BACKTEST, _REMEMBERED)
    return s


@pytest.fixture
def coordinator(store):
    c = UiStateCoordinator(store, debounce_ms=50_000)
    # `EPIC-017A` — production registers this eagerly in app_bootstrapper.py
    # (composition root), not inside SettingsPresenter or BackTestPresenter
    # anymore; this fixture stands in for that registration so the test still
    # exercises the real discard path SettingsPresenter._on_save() drives.
    c.register_config_binding(_BACKTEST, "DEFAULT_SYMBOLS", ("symbol",))
    c.register_config_binding(_BACKTEST, "DEFAULT_INTERVAL", ("timeframe",))
    return c


@pytest.fixture
def container(config, coordinator):
    c = Mock()
    c.resolve.side_effect = lambda interface: (
        config
        if interface is IConfig
        else coordinator
        if interface is UiStateCoordinator
        else Mock()
    )
    c.registrations.return_value = {UiStateCoordinator: object()}
    return c


@pytest.fixture
def presenter(qapp, container, request):
    view = SettingsView()
    view.resize(1200, 800)
    request.addfinalizer(view.deleteLater)
    return SettingsPresenter(view, container)


def test_saving_drops_the_remembered_values_settings_now_outranks(presenter, store):
    presenter._on_save()

    remaining = store.read(_BACKTEST)
    assert "symbol" not in remaining
    assert "timeframe" not in remaining


def test_saving_keeps_every_remembered_value_settings_does_not_own(presenter, store):
    """The reason `discard_keys()` had to exist. Dropping the whole slice to
    invalidate a symbol would take leverage, commission and the timezone with
    it — worse than the problem it solves."""
    presenter._on_save()

    remaining = store.read(_BACKTEST)
    assert remaining == {
        "long_leverage": 3.0,
        "commission": "0.05",
        "timezone": "UTC",
    }


def test_a_rejected_save_changes_nothing(qapp, container, store, request):
    """`_on_save()` bails out early on an empty symbol list. Nothing was
    written to config, so nothing may be discarded either."""
    view = SettingsView()
    view.resize(1200, 800)
    request.addfinalizer(view.deleteLater)
    presenter = SettingsPresenter(view, container)
    presenter._settings_view_model.defaultSymbols = "   "

    presenter._on_save()

    assert store.read(_BACKTEST) == _REMEMBERED


def test_saving_without_a_coordinator_still_works(qapp, config, request):
    """Every existing test builds this presenter against a container that
    knows nothing about persistence, and production did too before the
    coordinator was wired."""
    container = Mock()
    container.resolve.side_effect = lambda interface: (
        config if interface is IConfig else Mock()
    )
    container.registrations.return_value = {}
    view = SettingsView()
    view.resize(1200, 800)
    request.addfinalizer(view.deleteLater)
    presenter = SettingsPresenter(view, container)

    presenter._on_save()  # must not raise

    assert presenter._state_coordinator is None
