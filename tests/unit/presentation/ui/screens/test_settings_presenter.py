"""
Tests for the API & Credentials screen.

Migrated off QML onto QtWidgets (EPIC-005D) — was BOT-030 Phase 2 QML.
SettingsPresenter/SettingsViewModel are unchanged; only SettingsView's
rendering layer moved, so this file's "QML rendering" section below was
rewritten to assert against real QWidget children (found by objectName,
the same automation contract qml-rule.md already required of the QML
version) instead of `qml_item()`/`quick_widget.rootObject()`.

Uses the REAL SettingsViewModel rather than a mock: it is a plain state
holder with no I/O, so exercising it end-to-end catches property/signal
wiring mistakes that a Mock would silently absorb. Only IConfig (the actual
external dependency) is mocked — except in the persistence test below, which
uses a real ConfigManager to prove the disk-write path actually works, since
a Mock would happily "pass" even if save() were never called.

`EPIC-021B`: API Key/Secret no longer come from IConfig at all — they go
through `IExchangeCredentialsProvider`, closing `BUG-080`'s second problem
(`user_config.json` is git-tracked; a secret must never land there). Tests
below use the REAL `EnvFirstCredentialsProvider`/`SecretsFileSource` pointed
at a temp file rather than a hand-written double for the port — the same
"real object, substituted only at the transport/filesystem boundary"
preference the rest of this repo's test suite already follows, and it means
these tests exercise the actual precedence/redaction code, not a
reimplementation of it.
"""

import json
import os
from unittest.mock import Mock, call

import pytest
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QSpinBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.common.app_defaults import (
    FALLBACK_INTERVAL,
    FALLBACK_SYMBOL_OPTIONS,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_presenter import (
    SettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view import (
    SettingsView,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.infrastructure.config.config_manager import (
    ConfigManager,
)


@pytest.fixture(autouse=True)
def _no_env_credentials(monkeypatch):
    """Every test in this file controls credentials through the file source
    only — a leftover env var from the real machine running the suite must
    never leak in and flip `CredentialsSource.ENV` on underneath a test."""
    monkeypatch.delenv("BINANCE_FUTURES_TESTNET_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_FUTURES_TESTNET_API_SECRET", raising=False)


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
    # a test that should have failed — every other key falls back to None
    # (this fixture never configured `.get` at all before, so an unrelated
    # `config.get(...)` call used to return a truthy Mock() by accident).
    config.get.side_effect = lambda key, default=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )
    return config


@pytest.fixture
def credentials_provider(tmp_path):
    """A real provider, pre-seeded with a file-sourced key/secret pair — the
    file precedence branch, not `ENV`, so the fields stay editable and match
    the old fixture's `"test-key"`/`"test-secret"` expectations."""
    secrets_file = SecretsFileSource(str(tmp_path / "secrets.local.json"))
    secrets_file.write("test-key", "test-secret")
    return EnvFirstCredentialsProvider(secrets_file)


@pytest.fixture
def mock_container(mock_config, credentials_provider):
    container = Mock()

    def resolve_mock(interface):
        from sagittarius_engine.interfaces import IConfig

        if interface == IConfig:
            return mock_config
        if interface == IExchangeCredentialsProvider:
            return credentials_provider
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
# Loading from IConfig / IExchangeCredentialsProvider
# ---------------------------------------------------------------------------


def test_loads_fields_from_config_on_init(view_model):
    assert view_model.apiKey == "test-key"
    assert view_model.apiSecret == "test-secret"
    assert view_model.defaultSymbols == "BTCUSDT, ETHUSDT"
    assert view_model.defaultInterval == "1m"
    assert view_model.defaultSyncDays == 30


def test_credentials_source_label_and_lock_reflect_the_file_source(view_model):
    assert "secrets.local.json" in view_model.credentialsSourceLabel
    assert view_model.credentialsLocked is False


def test_an_env_var_locks_the_field_and_wins_over_the_file(
    qapp, mock_config, credentials_provider, monkeypatch, request
):
    """`EPIC-021B` §2.1/§2.3 — an environment variable always wins over the
    file, and the field must be locked: editing it here would silently be
    ignored by `resolve()` on next boot."""
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_KEY", "env-key")
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_SECRET", "env-secret")
    container = Mock()
    container.resolve.side_effect = lambda interface: (
        mock_config
        if interface.__name__ == "IConfig"
        else credentials_provider
        if interface is IExchangeCredentialsProvider
        else Mock()
    )
    view = SettingsView()
    request.addfinalizer(view.deleteLater)

    view_model = SettingsPresenter(view, container)._settings_view_model

    assert view_model.apiKey == "env-key"
    assert view_model.apiSecret == "env-secret"
    assert view_model.credentialsLocked is True
    assert "biến môi trường" in view_model.credentialsSourceLabel


def test_missing_config_keys_load_safely(
    qapp, mock_container, mock_config, tmp_path, request
):
    """A fresh install with an empty config must not crash the screen.

    The symbol/interval fields show the floor that is actually in effect, not
    a blank. They used to render empty, which was harmless while every install
    shipped DEFAULT_SYMBOLS/DEFAULT_INTERVAL in user_config.json and this path
    was unreachable. Once those keys stopped shipping, the blank became what a
    fresh install sees — on the one screen whose whole job is to show the
    current value — while every other screen quietly ran on its own floor.
    Credentials stay blank: no env var and no secrets.local.json content has
    no floor to fall back to.
    """
    mock_config.get_all.return_value = {}
    container = Mock()
    empty_provider = EnvFirstCredentialsProvider(
        SecretsFileSource(str(tmp_path / "does-not-exist.json"))
    )
    container.resolve.side_effect = lambda interface: (
        mock_config
        if interface.__name__ == "IConfig"
        else empty_provider
        if interface is IExchangeCredentialsProvider
        else Mock()
    )
    view = SettingsView()
    request.addfinalizer(view.deleteLater)

    view_model = SettingsPresenter(view, container)._settings_view_model

    assert view_model.apiKey == ""
    assert view_model.apiSecret == ""
    assert view_model.defaultSymbols == ", ".join(FALLBACK_SYMBOL_OPTIONS)
    assert view_model.defaultInterval == FALLBACK_INTERVAL
    assert view_model.defaultSyncDays == 1


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def test_save_writes_every_field_to_config(
    presenter, view_model, mock_config, credentials_provider
):
    mock_config.reset_mock()  # drop the constructor's get_all() call

    view_model.saveRequested.emit()

    mock_config.set.assert_has_calls(
        [
            call("DEFAULT_SYMBOLS", ["BTCUSDT", "ETHUSDT"]),
            call("DEFAULT_INTERVAL", "1m"),
            call("DEFAULT_SYNC_DAYS", 30),
        ]
    )
    # API_KEY/API_SECRET never reach IConfig — that is the git-tracked file.
    assert all(
        c.args[0] not in ("API_KEY", "API_SECRET")
        for c in mock_config.set.call_args_list
    )
    resolved = credentials_provider.resolve().credentials
    assert resolved.api_key == "test-key"
    assert resolved.api_secret == "test-secret"  # noqa: S105 - test fixture data
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


def test_save_writes_a_new_key_to_the_real_secrets_file(qapp, tmp_path, request):
    """
    The gap this closes: `IConfig.set()` alone was in-memory only for the
    config half, and for API Key/Secret specifically it never wrote anywhere
    real at all (`BUG-080`). Uses a real `ConfigManager` for the config half
    and a real `EnvFirstCredentialsProvider`/`SecretsFileSource` for
    credentials, so both disk-write paths are proven end to end rather than
    a Mock happily "passing" even if a write were never issued.
    """
    user_file = tmp_path / "user_config.json"
    # DEFAULT_SYMBOLS seeded non-empty: an empty value is rejected by Save's
    # own validation, which would make this test pass for the wrong reason.
    user_file.write_text(json.dumps({"DEFAULT_SYMBOLS": ["BTCUSDT"]}))

    config = ConfigManager()
    config.load_json(str(user_file), writable=True)

    secrets_file_path = tmp_path / "secrets.local.json"
    credentials_provider = EnvFirstCredentialsProvider(
        SecretsFileSource(str(secrets_file_path))
    )

    container = Mock()
    container.resolve.side_effect = lambda interface: (
        config
        if interface.__name__ == "IConfig"
        else credentials_provider
        if interface is IExchangeCredentialsProvider
        else Mock()
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
    view_model.apiSecret = "real-secret"
    view_model.saveRequested.emit()

    on_disk_config = json.loads(user_file.read_text())
    assert "API_KEY" not in on_disk_config
    assert "API_SECRET" not in on_disk_config

    on_disk_secrets = json.loads(secrets_file_path.read_text())
    assert on_disk_secrets == {"API_KEY": "real-key", "API_SECRET": "real-secret"}


def test_save_does_not_touch_the_secrets_file_when_an_env_var_is_locking_it(
    qapp, mock_config, tmp_path, monkeypatch, request
):
    """A locked field must not be written even if Save is pressed — the
    write would be indistinguishable from a real change, but `resolve()`
    would keep ignoring it in favour of the environment variable on the very
    next call."""
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_KEY", "env-key")
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_SECRET", "env-secret")
    secrets_file_path = tmp_path / "secrets.local.json"
    credentials_provider = EnvFirstCredentialsProvider(
        SecretsFileSource(str(secrets_file_path))
    )
    container = Mock()
    container.resolve.side_effect = lambda interface: (
        mock_config
        if interface.__name__ == "IConfig"
        else credentials_provider
        if interface is IExchangeCredentialsProvider
        else Mock()
    )
    view = SettingsView()
    request.addfinalizer(view.deleteLater)
    presenter = SettingsPresenter(view, container)
    view_model = presenter._settings_view_model

    view_model.saveRequested.emit()

    assert not secrets_file_path.exists()


def test_request_save_slot_triggers_the_same_path(presenter, view_model, mock_config):
    """`requestSave()` is what the Save button's `clicked` handler calls
    (see SettingsView.set_view_model) — proves that entry point reaches the
    presenter, not just the raw `saveRequested` signal."""
    mock_config.reset_mock()

    view_model.requestSave()

    mock_config.set.assert_any_call("DEFAULT_SYMBOLS", ["BTCUSDT", "ETHUSDT"])


# ---------------------------------------------------------------------------
# Widget rendering (EPIC-005D — was "QML rendering"; SettingsView is
# QtWidgets now, so these assert against real QWidget children instead of
# qml_item()/quick_widget.rootObject())
# ---------------------------------------------------------------------------


def test_screen_shows_config_values_on_real_widgets(presenter, qapp):
    """Proves the widget tree is actually built and bound to the view model
    — the values must be readable off the real QLineEdit/QSpinBox children,
    not just off Python."""
    view = presenter.view
    qapp.processEvents()

    assert view.findChild(QLineEdit, "txtApiKey").text() == "test-key"
    assert view.findChild(QLineEdit, "txtDefaultSymbols").text() == "BTCUSDT, ETHUSDT"
    assert view.findChild(QSpinBox, "spinDefaultSyncDays").value() == 30


def test_api_secret_is_masked_until_revealed(presenter, qapp):
    """Asserts what the user actually sees: `echoMode` is directly readable
    on a real QLineEdit (unlike the old QQuickTextInput, which had no
    PySide6 converter for it — this migration makes the more direct
    assertion possible instead of having to check `displayText`)."""
    qapp.processEvents()
    view = presenter.view
    secret_field = view.findChild(QLineEdit, "txtApiSecret")

    assert secret_field.text() == "test-secret"
    assert secret_field.echoMode() == QLineEdit.EchoMode.Password

    view.findChild(QPushButton, "btnRevealSecret").toggle()
    qapp.processEvents()

    assert secret_field.echoMode() == QLineEdit.EchoMode.Normal


def test_env_locked_credentials_disable_the_input_fields(
    qapp, mock_config, credentials_provider, monkeypatch, request
):
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_KEY", "env-key")
    monkeypatch.setenv("BINANCE_FUTURES_TESTNET_API_SECRET", "env-secret")
    container = Mock()
    container.resolve.side_effect = lambda interface: (
        mock_config
        if interface.__name__ == "IConfig"
        else credentials_provider
        if interface is IExchangeCredentialsProvider
        else Mock()
    )
    view = SettingsView()
    view.resize(1200, 800)
    view.show()
    request.addfinalizer(view.deleteLater)
    SettingsPresenter(view, container)
    qapp.processEvents()

    assert view.findChild(QLineEdit, "txtApiKey").isReadOnly() is True
    assert view.findChild(QLineEdit, "txtApiSecret").isReadOnly() is True
    label = view.findChild(QLabel, "lblCredentialsSource")
    assert "biến môi trường" in label.text()


def test_save_button_click_writes_config(presenter, qapp, mock_config):
    """Full chain: real QPushButton click -> viewModel.requestSave() ->
    presenter -> IConfig."""
    qapp.processEvents()
    mock_config.reset_mock()

    presenter.view.findChild(QPushButton, "btnSaveCredentials").click()
    qapp.processEvents()

    mock_config.set.assert_any_call("DEFAULT_SYMBOLS", ["BTCUSDT", "ETHUSDT"])


def test_view_model_writes_flow_back_into_a_save(
    presenter, view_model, mock_config, credentials_provider
):
    """
    The write half of the two-way binding: the widget's `textEdited`/
    `valueChanged` handlers assign to these properties (see
    SettingsView._on_*_edited), so a value written that way must be what
    Save persists. Drives the same property the handler writes rather than
    simulating real keystrokes — the widget side of that wiring is covered
    by the round-trip test below.
    """
    mock_config.reset_mock()

    view_model.apiKey = "edited-key"
    view_model.defaultInterval = "15m"
    view_model.defaultSyncDays = 90
    view_model.saveRequested.emit()

    mock_config.set.assert_any_call("DEFAULT_INTERVAL", "15m")
    mock_config.set.assert_any_call("DEFAULT_SYNC_DAYS", 90)
    assert credentials_provider.resolve().credentials.api_key == "edited-key"


def test_editing_a_widget_reaches_the_view_model(presenter, view_model, qapp):
    """The other half of the round-trip, driven through the real widget this
    time: typing in the QLineEdit must update the view model, proving
    `textEdited` is actually connected (not just the property-level path
    the test above exercises)."""
    qapp.processEvents()
    field = presenter.view.findChild(QLineEdit, "txtApiKey")

    field.setText("typed-key")
    field.textEdited.emit("typed-key")

    assert view_model.apiKey == "typed-key"


def test_updating_the_view_model_refreshes_the_widget(presenter, qapp):
    """The read half: a Python-side change must reach the rendered widget
    (proves the `*Changed` NOTIFY signal is wired to the widget, not just
    read once at construction)."""
    qapp.processEvents()

    presenter._settings_view_model.apiKey = "rotated-key"
    qapp.processEvents()

    assert presenter.view.findChild(QLineEdit, "txtApiKey").text() == "rotated-key"


def test_status_label_reflects_success_and_error_colour(presenter, view_model, qapp):
    """Regression coverage for the QML version's status-line styling logic
    (statusIsError -> danger/success colour), now driven through
    SettingsView._apply_status()."""
    qapp.processEvents()
    status_label = presenter.view.findChild(QLabel, "lblStatus")

    view_model.set_status("all good", is_error=False)
    qapp.processEvents()
    assert status_label.text() == "all good"
    assert Palette.SUCCESS in status_label.styleSheet()

    view_model.set_status("broken", is_error=True)
    qapp.processEvents()
    assert status_label.text() == "broken"
    assert Palette.DANGER in status_label.styleSheet()
