"""
Tests for the API & Credentials screen (BOT-030 Phase 2 — QML).

Uses the REAL SettingsViewModel rather than a mock: it is a plain state
holder with no I/O, so exercising it end-to-end catches property/signal
wiring mistakes that a Mock would silently absorb. Only IConfig (the actual
external dependency) is mocked — except in the persistence test below, which
uses a real ConfigManager to prove the disk-write path actually works, since
a Mock would happily "pass" even if save() were never called.
"""

import json
import os
from unittest.mock import Mock, call

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_presenter import (
    SettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view import (
    SettingsView,
)
from sagittarius_engine.infrastructure.config.config_manager import (
    ConfigManager,
)


@pytest.fixture
def mock_config():
    config = Mock()
    config.get_all.return_value = {
        "API_KEY": "test-key",
        "API_SECRET": "test-secret",
        "DEFAULT_SYMBOLS": ["BTCUSDT", "ETHUSDT"],
        "DEFAULT_INTERVAL": "1m",
        "DEFAULT_SYNC_DAYS": 30,
    }
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
    view = SettingsView()
    # Sized and shown deliberately: QML layouts can't resolve positions in a
    # 0x0 widget, so geometry assertions against an unsized view would be
    # meaningless (and misleadingly "pass" or fail for the wrong reason).
    view.resize(1200, 800)
    view.show()
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return SettingsPresenter(view, mock_container)


@pytest.fixture
def view_model(presenter):
    return presenter._settings_view_model


# ---------------------------------------------------------------------------
# Loading from IConfig
# ---------------------------------------------------------------------------


def test_loads_fields_from_config_on_init(view_model):
    assert view_model.apiKey == "test-key"
    assert view_model.apiSecret == "test-secret"
    assert view_model.defaultSymbols == "BTCUSDT, ETHUSDT"
    assert view_model.defaultInterval == "1m"
    assert view_model.defaultSyncDays == 30


def test_missing_config_keys_load_safely(qapp, mock_container, mock_config, request):
    """A fresh install with an empty config must not crash the screen."""
    mock_config.get_all.return_value = {}
    view = SettingsView()
    request.addfinalizer(view.deleteLater)

    view_model = SettingsPresenter(view, mock_container)._settings_view_model

    assert view_model.apiKey == ""
    assert view_model.defaultSymbols == ""
    assert view_model.defaultSyncDays == 1


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def test_save_writes_every_field_to_config(presenter, view_model, mock_config):
    mock_config.reset_mock()  # drop the constructor's get_all() call

    view_model.saveRequested.emit()

    mock_config.set.assert_has_calls(
        [
            call("API_KEY", "test-key"),
            call("API_SECRET", "test-secret"),
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


def test_save_persists_to_disk_through_a_real_config_manager(qapp, tmp_path, request):
    """
    The gap this closes: IConfig.set() alone was in-memory only, so a real
    ConfigManager is used here (not the mock_config fixture) to prove Save
    actually reaches the writable JSON file on disk, end to end.
    """
    user_file = tmp_path / "user_config.json"
    # DEFAULT_SYMBOLS seeded non-empty: an empty value is rejected by Save's
    # own validation, which would make this test pass for the wrong reason.
    user_file.write_text(json.dumps({"DEFAULT_SYMBOLS": ["BTCUSDT"]}))

    config = ConfigManager()
    config.load_json(str(user_file), writable=True)

    container = Mock()
    container.resolve.side_effect = lambda interface: (
        config if interface.__name__ == "IConfig" else Mock()
    )

    view = SettingsView()
    view.resize(1200, 800)
    view.show()
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)

    # Keeping `presenter` alive matters: saveRequested is connected to its
    # bound method, and PySide6 doesn't keep that connection's target alive
    # on its own — an unreferenced presenter gets garbage-collected right
    # after construction, silently dropping the connection before emit().
    presenter = SettingsPresenter(view, container)
    view_model = presenter._settings_view_model
    view_model.apiKey = "real-key"
    view_model.saveRequested.emit()

    on_disk = json.loads(user_file.read_text())
    assert on_disk["API_KEY"] == "real-key"


def test_qml_request_save_slot_triggers_the_same_path(
    presenter, view_model, mock_config
):
    """`requestSave()` is what the QML Save button calls — proves the QML
    entry point reaches the presenter, not just the raw signal."""
    mock_config.reset_mock()

    view_model.requestSave()

    mock_config.set.assert_any_call("API_KEY", "test-key")


# ---------------------------------------------------------------------------
# QML rendering
# ---------------------------------------------------------------------------


def test_qml_screen_loads_and_shows_config_values(presenter, qml_item, qapp):
    """Proves the QML document parses and binds to the view model — the
    values must be readable off the real QML items, not just off Python."""
    view = presenter.view
    qapp.processEvents()

    assert view.quick_widget.errors() == []
    root = view.quick_widget.rootObject()
    assert root is not None

    assert qml_item(root, "txtApiKey").property("text") == "test-key"
    assert qml_item(root, "txtDefaultSymbols").property("text") == "BTCUSDT, ETHUSDT"
    assert qml_item(root, "spinDefaultSyncDays").property("value") == 30


def test_api_secret_is_masked_until_revealed(presenter, qml_item, qapp):
    """
    Asserts what the user actually sees: `displayText` is the rendered
    string, so a masked field shows bullets while `text` still holds the
    real secret. (Checking `echoMode` directly isn't possible — PySide6 has
    no converter for QQuickTextInput::EchoMode — and this is the more
    meaningful assertion anyway.)
    """
    qapp.processEvents()
    root = presenter.view.quick_widget.rootObject()
    secret_field = qml_item(root, "txtApiSecret")

    assert secret_field.property("text") == "test-secret"
    assert secret_field.property("displayText") != "test-secret"

    qml_item(root, "btnRevealSecret").toggle()
    qapp.processEvents()

    assert secret_field.property("displayText") == "test-secret"


def test_qml_save_button_click_writes_config(presenter, qml_item, qapp, mock_config):
    """Full chain: QML button -> viewModel.requestSave() -> presenter -> IConfig."""
    qapp.processEvents()
    mock_config.reset_mock()

    qml_item(
        presenter.view.quick_widget.rootObject(), "btnSaveCredentials"
    ).clicked.emit()
    qapp.processEvents()

    mock_config.set.assert_any_call("API_KEY", "test-key")


def test_view_model_writes_flow_back_into_a_save(presenter, view_model, mock_config):
    """
    The write half of the two-way binding: QML's `onTextEdited` handlers
    assign to these properties, so a value written that way must be what
    Save persists. (Simulating real keystrokes into a QML TextField isn't
    practical here, so this drives the same property the delegate writes —
    the QML side of that wiring is covered by the render test above.)
    """
    mock_config.reset_mock()

    view_model.apiKey = "edited-key"
    view_model.defaultInterval = "15m"
    view_model.defaultSyncDays = 90
    view_model.saveRequested.emit()

    mock_config.set.assert_any_call("API_KEY", "edited-key")
    mock_config.set.assert_any_call("DEFAULT_INTERVAL", "15m")
    mock_config.set.assert_any_call("DEFAULT_SYNC_DAYS", 90)


def test_status_line_is_laid_out_below_the_form_not_stacked_on_it(
    presenter, qml_item, qapp
):
    """
    Regression test: the status label used `visible: text !== ""`, and a
    ColumnLayout skips invisible children — flipping that binding when a
    save produced a message did NOT re-run the layout, leaving the label
    stranded at y=0, drawn on top of the warning banner. Asserts it ends up
    BELOW the last form row once it has text.
    """
    qapp.processEvents()
    root = presenter.view.quick_widget.rootObject()

    presenter._settings_view_model.saveRequested.emit()
    qapp.processEvents()

    status = qml_item(root, "lblStatus")
    sync_days = qml_item(root, "spinDefaultSyncDays")
    assert status.property("text") != ""

    status_y = status.mapToItem(None, 0, 0).y()
    last_row_y = sync_days.mapToItem(None, 0, 0).y()
    assert status_y > last_row_y


def test_updating_the_view_model_refreshes_the_qml_field(presenter, qml_item, qapp):
    """The read half: a Python-side change must reach the rendered QML item
    (proves the NOTIFY signal is wired, not just the getter)."""
    qapp.processEvents()
    root = presenter.view.quick_widget.rootObject()

    presenter._settings_view_model.apiKey = "rotated-key"
    qapp.processEvents()

    assert qml_item(root, "txtApiKey").property("text") == "rotated-key"
