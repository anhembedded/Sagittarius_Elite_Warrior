"""Tests for the Market Data settings section (`EPIC-025E` PR 4.4e).

Split off `tests/unit/presentation/ui/screens/test_settings_presenter.py`,
keeping only what this module owns: default symbols, default interval,
default sync days, and their widgets. `trading`'s slice (credentials,
connection check) moved to
`tests/unit/modules/trading/ui/settings/test_trading_settings_presenter.py`.
Venue coverage lives in `test_market_data_settings_venue.py` in this same
package.

Uses the REAL `MarketDataSettingsViewModel` rather than a mock: it is a
plain state holder with no I/O, so exercising it end-to-end catches
property/signal wiring mistakes that a Mock would silently absorb. Only
`IConfig` (the actual external dependency) is mocked — except in the
persistence test below, which uses a real `ConfigManager` to prove the
disk-write path actually works, since a Mock would happily "pass" even if
`save()` were never called.
"""

from __future__ import annotations

import json
import os
from unittest.mock import Mock, call

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QSpinBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.modules.market_data.ui.settings.market_data_settings_presenter import (
    MarketDataSettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.settings.market_data_settings_view import (
    MarketDataSettingsView,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_INTERVAL,
    FALLBACK_SYMBOL_OPTIONS,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import semantic_colour
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


@pytest.fixture
def mock_config():
    config = Mock()
    config.get_all.return_value = {
        "DEFAULT_SYMBOLS": ["BTCUSDT", "ETHUSDT"],
        "DEFAULT_INTERVAL": "1m",
        "DEFAULT_SYNC_DAYS": 30,
    }
    # BOT-066: dev.mode on for the whole suite, so any exception a
    # @safe_ui_action-decorated slot swallows re-raises instead of passing
    # a test that should have failed.
    config.get.side_effect = lambda key, default=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )
    return config


@pytest.fixture
def mock_container(mock_config):
    container = Mock()

    def resolve_mock(interface):
        from sagittarius_engine.interfaces import IConfig

        if interface == IConfig:
            return mock_config
        return Mock()

    container.resolve.side_effect = resolve_mock
    return container


@pytest.fixture
def presenter(qapp, mock_container, request):
    view = MarketDataSettingsView()
    view.resize(1200, 800)
    view.show()
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return MarketDataSettingsPresenter(view, mock_container)


@pytest.fixture
def view_model(presenter):
    return presenter._settings_view_model


# ---------------------------------------------------------------------------
# Loading from IConfig
# ---------------------------------------------------------------------------


def test_loads_fields_from_config_on_init(view_model):
    assert view_model.defaultSymbols == "BTCUSDT, ETHUSDT"
    assert view_model.defaultInterval == "1m"
    assert view_model.defaultSyncDays == 30


def test_missing_config_keys_load_safely(qapp, mock_container, mock_config, request):
    """A fresh install with an empty config must not crash the screen.

    The symbol/interval fields show the floor that is actually in effect,
    not a blank. They used to render empty, which was harmless while every
    install shipped DEFAULT_SYMBOLS/DEFAULT_INTERVAL in user_config.json and
    this path was unreachable. Once those keys stopped shipping, the blank
    became what a fresh install sees — on the one screen whose whole job is
    to show the current value — while every other screen quietly ran on
    its own floor.
    """
    mock_config.get_all.return_value = {}
    view = MarketDataSettingsView()
    request.addfinalizer(view.deleteLater)

    view_model = MarketDataSettingsPresenter(view, mock_container)._settings_view_model

    assert view_model.defaultSymbols == ", ".join(FALLBACK_SYMBOL_OPTIONS)
    assert view_model.defaultInterval == FALLBACK_INTERVAL
    assert view_model.defaultSyncDays == 1


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def test_save_writes_every_field_to_config(presenter, view_model, mock_config):
    mock_config.reset_mock()  # drop the constructor's get_all() call

    view_model.saveRequested.emit()

    mock_config.set.assert_has_calls(
        [
            call("DEFAULT_SYMBOLS", ["BTCUSDT", "ETHUSDT"]),
            call("DEFAULT_INTERVAL", "1m"),
            call("DEFAULT_SYNC_DAYS", 30),
        ]
    )
    assert view_model.statusIsError is False
    assert view_model.statusMessage != ""


def test_save_trims_and_splits_symbols(presenter, view_model, mock_config):
    mock_config.reset_mock()
    view_model.defaultSymbols = " BTCUSDT ,  SOLUSDT ,"

    view_model.saveRequested.emit()

    mock_config.set.assert_any_call("DEFAULT_SYMBOLS", ["BTCUSDT", "SOLUSDT"])


def test_save_with_empty_symbols_is_rejected_without_writing_anything(
    presenter, view_model, mock_config
):
    """A rejected save must not apply partially — nothing reaches IConfig."""
    mock_config.reset_mock()
    view_model.defaultSymbols = "   ,  , "

    view_model.saveRequested.emit()

    mock_config.set.assert_not_called()
    assert view_model.statusIsError is True
    assert view_model.statusMessage != ""


def test_save_writes_to_the_real_config_file(qapp, tmp_path, request):
    """Uses a real `ConfigManager` so the disk-write path is proven end to
    end rather than a Mock happily "passing" even if a write were never
    issued."""
    user_file = tmp_path / "user_config.json"
    user_file.write_text(json.dumps({"DEFAULT_SYMBOLS": ["BTCUSDT"]}))

    config = ConfigManager()
    config.load_json(str(user_file), writable=True)

    container = Mock()
    container.resolve.side_effect = lambda interface: (
        config if interface.__name__ == "IConfig" else Mock()
    )

    view = MarketDataSettingsView()
    view.resize(1200, 800)
    view.show()
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)

    # Keeping `presenter` alive matters: saveRequested is connected to its
    # bound method, and PySide6 doesn't keep that connection's target alive
    # on its own — an unreferenced presenter gets garbage-collected right
    # after construction, silently dropping the connection before emit().
    presenter = MarketDataSettingsPresenter(view, container)
    view_model = presenter._settings_view_model
    view_model.defaultSymbols = "ETHUSDT"
    view_model.saveRequested.emit()

    on_disk_config = json.loads(user_file.read_text())
    assert on_disk_config["DEFAULT_SYMBOLS"] == ["ETHUSDT"]


def test_request_save_slot_triggers_the_same_path(presenter, view_model, mock_config):
    """`requestSave()` is what the Save button's `clicked` handler calls
    (see `MarketDataSettingsView.set_view_model`) — proves that entry point
    reaches the presenter, not just the raw `saveRequested` signal."""
    mock_config.reset_mock()

    view_model.requestSave()

    mock_config.set.assert_any_call("DEFAULT_SYMBOLS", ["BTCUSDT", "ETHUSDT"])


# ---------------------------------------------------------------------------
# Widget rendering (real QWidget children, found by objectName)
# ---------------------------------------------------------------------------


def test_screen_shows_config_values_on_real_widgets(presenter, qapp):
    """Proves the widget tree is actually built and bound to the view model
    — the values must be readable off the real QLineEdit/QSpinBox children,
    not just off Python."""
    view = presenter.view
    qapp.processEvents()

    assert view.findChild(QLineEdit, "txtDefaultSymbols").text() == "BTCUSDT, ETHUSDT"
    assert view.findChild(QSpinBox, "spinDefaultSyncDays").value() == 30


def test_save_button_click_writes_config(presenter, qapp, mock_config):
    """Full chain: real QPushButton click -> viewModel.requestSave() ->
    presenter -> IConfig."""
    qapp.processEvents()
    mock_config.reset_mock()

    presenter.view.findChild(QPushButton, "btnSaveMarketDataSettings").click()
    qapp.processEvents()

    mock_config.set.assert_any_call("DEFAULT_SYMBOLS", ["BTCUSDT", "ETHUSDT"])


def test_view_model_writes_flow_back_into_a_save(presenter, view_model, mock_config):
    """
    The write half of the two-way binding: the widget's `textEdited`/
    `valueChanged` handlers assign to these properties (see
    `MarketDataSettingsView._on_*_edited`), so a value written that way must
    be what Save persists. Drives the same property the handler writes
    rather than simulating real keystrokes — the widget side of that wiring
    is covered by the round-trip test below.
    """
    mock_config.reset_mock()

    view_model.defaultInterval = "15m"
    view_model.defaultSyncDays = 90
    view_model.saveRequested.emit()

    mock_config.set.assert_any_call("DEFAULT_INTERVAL", "15m")
    mock_config.set.assert_any_call("DEFAULT_SYNC_DAYS", 90)


def test_editing_a_widget_reaches_the_view_model(presenter, view_model, qapp):
    """The other half of the round-trip, driven through the real widget this
    time: typing in the QLineEdit must update the view model, proving
    `textEdited` is actually connected (not just the property-level path
    the test above exercises)."""
    qapp.processEvents()
    field = presenter.view.findChild(QLineEdit, "txtDefaultSymbols")

    field.setText("SOLUSDT")
    field.textEdited.emit("SOLUSDT")

    assert view_model.defaultSymbols == "SOLUSDT"


def test_updating_the_view_model_refreshes_the_widget(presenter, qapp):
    """The read half: a Python-side change must reach the rendered widget
    (proves the `*Changed` NOTIFY signal is wired to the widget, not just
    read once at construction)."""
    qapp.processEvents()

    presenter._settings_view_model.defaultSymbols = "SOLUSDT"
    qapp.processEvents()

    assert presenter.view.findChild(QLineEdit, "txtDefaultSymbols").text() == "SOLUSDT"


def test_status_label_reflects_success_and_error_colour(presenter, view_model, qapp):
    qapp.processEvents()
    status_label = presenter.view.findChild(QLabel, "lblMarketDataSettingsStatus")

    def _text_colour() -> QColor:
        return status_label.palette().color(QPalette.ColorRole.WindowText)

    view_model.set_status("all good", is_error=False)
    qapp.processEvents()
    assert status_label.text() == "all good"
    assert _text_colour() == QColor(semantic_colour("success"))

    view_model.set_status("broken", is_error=True)
    qapp.processEvents()
    assert status_label.text() == "broken"
    assert _text_colour() == QColor(semantic_colour("danger"))
