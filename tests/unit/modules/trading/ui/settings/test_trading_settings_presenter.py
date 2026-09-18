"""Tests for the Trading settings section (`EPIC-025E` PR 4.4e).

Split off `tests/unit/presentation/ui/screens/test_settings_presenter.py`,
keeping only what this module owns: API credentials and their widgets.
`market_data`'s slice (default symbols/interval/sync days) moved to
`tests/unit/modules/market_data/ui/settings/test_market_data_settings_presenter.py`.
Venue-lock and connection-check coverage live in their own files in this
same package.

Uses the REAL `TradingSettingsViewModel` rather than a mock, and the REAL
`EnvFirstCredentialsProvider`/`SecretsFileSource` pointed at a temp file
rather than a hand-written double for the port, for the same reasons the
original file gave.
"""

from __future__ import annotations

import json
import os
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_presenter import (
    TradingSettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.trading_settings_view import (
    TradingSettingsView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import Palette
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


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
    # BOT-066: dev.mode on for the whole suite, so any exception a
    # @safe_ui_action-decorated slot swallows re-raises instead of passing
    # a test that should have failed.
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
def session_state() -> FakeTradingSession:
    """`BOT-125` — a real answer so `_venue_locked()` reads a real bool.
    Starts disabled, which is what a fresh session guarantees."""
    return FakeTradingSession()


@pytest.fixture
def mock_container(mock_config, credentials_provider, session_state):
    container = Mock()

    def resolve_mock(interface):
        from sagittarius_engine.interfaces import IConfig

        if interface == IConfig:
            return mock_config
        if interface == IExchangeCredentialsProvider:
            return credentials_provider
        if interface is ITradingSession:
            return session_state
        if interface is IAccountSnapshot:
            return FakeAccountSnapshot()
        return Mock()

    container.resolve.side_effect = resolve_mock
    return container


@pytest.fixture
def presenter(qapp, mock_container, request):
    view = TradingSettingsView()
    # Sized and shown deliberately: geometry assertions against an unsized
    # view would be meaningless (and misleadingly "pass" or fail for the
    # wrong reason).
    view.resize(1200, 800)
    view.show()
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return TradingSettingsPresenter(view, mock_container)


@pytest.fixture
def view_model(presenter):
    return presenter._settings_view_model


# ---------------------------------------------------------------------------
# Loading from IExchangeCredentialsProvider
# ---------------------------------------------------------------------------


def test_loads_fields_from_credentials_provider_on_init(view_model):
    assert view_model.apiKey == "test-key"
    assert view_model.apiSecret == "test-secret"


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
        else FakeTradingSession()
        if interface is ITradingSession
        else FakeAccountSnapshot()
        if interface is IAccountSnapshot
        else Mock()
    )
    view = TradingSettingsView()
    request.addfinalizer(view.deleteLater)

    view_model = TradingSettingsPresenter(view, container)._settings_view_model

    assert view_model.apiKey == "env-key"
    assert view_model.apiSecret == "env-secret"
    assert view_model.credentialsLocked is True
    assert "environment variable" in view_model.credentialsSourceLabel


def test_missing_credentials_load_safely(qapp, mock_config, tmp_path, request):
    """A fresh install with no key/secret anywhere must not crash the
    screen. Credentials stay blank: no env var and no secrets.local.json
    content has no floor to fall back to."""
    container = Mock()
    empty_provider = EnvFirstCredentialsProvider(
        SecretsFileSource(str(tmp_path / "does-not-exist.json"))
    )
    container.resolve.side_effect = lambda interface: (
        mock_config
        if interface.__name__ == "IConfig"
        else empty_provider
        if interface is IExchangeCredentialsProvider
        else FakeTradingSession()
        if interface is ITradingSession
        else FakeAccountSnapshot()
        if interface is IAccountSnapshot
        else Mock()
    )
    view = TradingSettingsView()
    request.addfinalizer(view.deleteLater)

    view_model = TradingSettingsPresenter(view, container)._settings_view_model

    assert view_model.apiKey == ""
    assert view_model.apiSecret == ""


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def test_save_writes_credentials_to_the_provider(
    presenter, view_model, credentials_provider
):
    view_model.saveRequested.emit()

    resolved = credentials_provider.resolve().credentials
    assert resolved.api_key == "test-key"
    assert resolved.api_secret == "test-secret"  # noqa: S105 - test fixture data
    assert view_model.statusIsError is False
    assert view_model.statusMessage != ""


def test_save_writes_a_new_key_to_the_real_secrets_file(qapp, tmp_path, request):
    """
    The gap this closes: API Key/Secret never wrote anywhere real at all
    (`BUG-080`). Uses a real `EnvFirstCredentialsProvider`/`SecretsFileSource`
    so the disk-write path is proven end to end rather than a Mock happily
    "passing" even if a write were never issued.
    """
    secrets_file_path = tmp_path / "secrets.local.json"
    credentials_provider = EnvFirstCredentialsProvider(
        SecretsFileSource(str(secrets_file_path))
    )

    config = ConfigManager()
    container = Mock()
    container.resolve.side_effect = lambda interface: (
        config
        if interface.__name__ == "IConfig"
        else credentials_provider
        if interface is IExchangeCredentialsProvider
        else FakeTradingSession()
        if interface is ITradingSession
        else FakeAccountSnapshot()
        if interface is IAccountSnapshot
        else Mock()
    )

    view = TradingSettingsView()
    view.resize(1200, 800)
    view.show()
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)

    # Keeping `presenter` alive matters: saveRequested is connected to its
    # bound method, and PySide6 doesn't keep that connection's target alive
    # on its own — an unreferenced presenter gets garbage-collected right
    # after construction, silently dropping the connection before emit().
    presenter = TradingSettingsPresenter(view, container)
    view_model = presenter._settings_view_model
    view_model.apiKey = "real-key"
    view_model.apiSecret = "real-secret"
    view_model.saveRequested.emit()

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
        else FakeTradingSession()
        if interface is ITradingSession
        else FakeAccountSnapshot()
        if interface is IAccountSnapshot
        else Mock()
    )
    view = TradingSettingsView()
    request.addfinalizer(view.deleteLater)
    presenter = TradingSettingsPresenter(view, container)
    view_model = presenter._settings_view_model

    view_model.saveRequested.emit()

    assert not secrets_file_path.exists()


def test_request_save_slot_triggers_the_same_path(
    presenter, view_model, credentials_provider
):
    """`requestSave()` is what the Save button's `clicked` handler calls
    (see `TradingSettingsView.set_view_model`) — proves that entry point
    reaches the presenter, not just the raw `saveRequested` signal."""
    view_model.apiKey = "requested-key"

    view_model.requestSave()

    assert credentials_provider.resolve().credentials.api_key == "requested-key"


# ---------------------------------------------------------------------------
# Widget rendering (real QWidget children, found by objectName)
# ---------------------------------------------------------------------------


def test_screen_shows_config_values_on_real_widgets(presenter, qapp):
    """Proves the widget tree is actually built and bound to the view model
    — the values must be readable off the real QLineEdit children, not just
    off Python."""
    view = presenter.view
    qapp.processEvents()

    assert view.findChild(QLineEdit, "txtApiKey").text() == "test-key"


def test_api_secret_is_masked_until_revealed(presenter, qapp):
    """Asserts what the user actually sees: `echoMode` is directly readable
    on a real QLineEdit."""
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
        else FakeTradingSession()
        if interface is ITradingSession
        else FakeAccountSnapshot()
        if interface is IAccountSnapshot
        else Mock()
    )
    view = TradingSettingsView()
    view.resize(1200, 800)
    view.show()
    request.addfinalizer(view.deleteLater)
    TradingSettingsPresenter(view, container)
    qapp.processEvents()

    assert view.findChild(QLineEdit, "txtApiKey").isReadOnly() is True
    assert view.findChild(QLineEdit, "txtApiSecret").isReadOnly() is True
    label = view.findChild(QLabel, "lblCredentialsSource")
    assert "environment variable" in label.text()


def test_save_button_click_writes_credentials(presenter, qapp, credentials_provider):
    """Full chain: real QPushButton click -> viewModel.requestSave() ->
    presenter -> IExchangeCredentialsProvider."""
    qapp.processEvents()
    field = presenter.view.findChild(QLineEdit, "txtApiKey")
    field.setText("clicked-key")
    field.textEdited.emit("clicked-key")

    presenter.view.findChild(QPushButton, "btnSaveCredentials").click()
    qapp.processEvents()

    assert credentials_provider.resolve().credentials.api_key == "clicked-key"


def test_view_model_writes_flow_back_into_a_save(
    presenter, view_model, credentials_provider
):
    """The write half of the two-way binding: the widget's `textEdited`
    handler assigns to this property (see
    `TradingSettingsView._on_api_key_edited`), so a value written that way
    must be what Save persists."""
    view_model.apiKey = "edited-key"
    view_model.saveRequested.emit()

    assert credentials_provider.resolve().credentials.api_key == "edited-key"


def test_editing_a_widget_reaches_the_view_model(presenter, view_model, qapp):
    """The other half of the round-trip, driven through the real widget this
    time: typing in the QLineEdit must update the view model, proving
    `textEdited` is actually connected."""
    qapp.processEvents()
    field = presenter.view.findChild(QLineEdit, "txtApiKey")

    field.setText("typed-key")
    field.textEdited.emit("typed-key")

    assert view_model.apiKey == "typed-key"


def test_updating_the_view_model_refreshes_the_widget(presenter, qapp):
    """The read half: a Python-side change must reach the rendered widget
    (proves the `apiKeyChanged` NOTIFY signal is wired to the widget, not
    just read once at construction)."""
    qapp.processEvents()

    presenter._settings_view_model.apiKey = "rotated-key"
    qapp.processEvents()

    assert presenter.view.findChild(QLineEdit, "txtApiKey").text() == "rotated-key"


def test_status_label_reflects_success_and_error_colour(presenter, view_model, qapp):
    qapp.processEvents()
    status_label = presenter.view.findChild(QLabel, "lblTradingSettingsStatus")

    view_model.set_status("all good", is_error=False)
    qapp.processEvents()
    assert status_label.text() == "all good"
    assert Palette.SUCCESS in status_label.styleSheet()

    view_model.set_status("broken", is_error=True)
    qapp.processEvents()
    assert status_label.text() == "broken"
    assert Palette.DANGER in status_label.styleSheet()
