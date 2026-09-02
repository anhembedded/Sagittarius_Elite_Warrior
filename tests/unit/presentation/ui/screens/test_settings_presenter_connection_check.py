"""`EPIC-021D` — Settings screen's "Kiểm tra kết nối" button.

Calls `SettingsPresenter._run_check_connection()` directly rather than
going through the real `IThreadManager` pool — same pattern
`test_gap_coordinator.py` uses for its own background actions: the worker
method is plain, synchronous, testable code; only its *submission* onto a
background thread is infrastructure, and that part is a `Mock` here.
Because it runs synchronously in the test's own thread, `Signal.emit()`
below invokes connected slots immediately (Qt only queues cross-thread), so
the full begin -> emit -> ownership-check -> ViewModel-update chain is
exercised for real, not re-implemented.
"""

from __future__ import annotations

import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QLabel, QPushButton
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.env_first_credentials_provider import (
    EnvFirstCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.infrastructure.credentials.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_presenter import (
    SettingsPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.settings_view import (
    SettingsView,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

_SUCCESS_STATUS = ExchangeConnectionStatus(
    venue=TradingVenue.FUTURES_TESTNET,
    reachable=True,
    failure=None,
    server_time_skew_ms=100,
    usdt_balance=None,
    position_mode=None,
    margin_type=None,
    open_position_count=0,
)


@pytest.fixture
def mock_config():
    config = Mock()
    config.get_all.return_value = {
        "DEFAULT_SYMBOLS": ["BTCUSDT"],
        "DEFAULT_INTERVAL": "1m",
        "DEFAULT_SYNC_DAYS": 30,
    }
    config.get.side_effect = lambda key, default=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )
    return config


@pytest.fixture
def mock_dispatcher():
    return Mock()


@pytest.fixture
def mock_thread_manager():
    return Mock()


@pytest.fixture
def credentials_provider(tmp_path):
    return EnvFirstCredentialsProvider(SecretsFileSource(str(tmp_path / "s.json")))


@pytest.fixture
def container(mock_config, mock_dispatcher, mock_thread_manager, credentials_provider):
    from sagittarius_engine.interfaces import IConfig, IDispatcher

    c = Mock()

    def resolve(interface):
        if interface is IConfig:
            return mock_config
        if interface is IDispatcher:
            return mock_dispatcher
        if interface is IThreadManager:
            return mock_thread_manager
        if interface is IExchangeCredentialsProvider:
            return credentials_provider
        return Mock()

    c.resolve.side_effect = resolve
    return c


@pytest.fixture
def presenter(qapp, container, request):
    view = SettingsView()
    view.resize(1200, 800)
    request.addfinalizer(view.deleteLater)
    return SettingsPresenter(view, container)


def test_clicking_check_connection_submits_a_background_task_and_locks_the_button(
    presenter, mock_thread_manager
):
    view_model = presenter._settings_view_model

    view_model.checkConnectionRequested.emit()

    assert view_model.connectionChecking is True
    mock_thread_manager.submit.assert_called_once()
    submitted_callable = mock_thread_manager.submit.call_args[0][0]
    assert submitted_callable == presenter._run_check_connection


def test_a_successful_check_populates_the_result_and_unlocks_the_button(
    presenter, mock_dispatcher
):
    mock_dispatcher.dispatch.return_value = _SUCCESS_STATUS
    view_model = presenter._settings_view_model
    view_model.checkConnectionRequested.emit()
    action_id = presenter._connection_check_tracker.active_action.action_id

    presenter._run_check_connection(action_id)

    mock_dispatcher.dispatch.assert_called_once_with(
        GetExchangeConnectionStatusQuery, GetExchangeConnectionStatusQuery()
    )
    assert view_model.connectionChecking is False
    assert "FUTURES_TESTNET" in view_model.connectionResultText
    assert view_model.connectionResultIsError is False


def test_a_failed_status_renders_as_an_error(presenter, mock_dispatcher):
    failed_status = ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=False,
        failure=ConnectionFailureKind.NOT_CONFIGURED,
        server_time_skew_ms=None,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )
    mock_dispatcher.dispatch.return_value = failed_status
    view_model = presenter._settings_view_model
    view_model.checkConnectionRequested.emit()
    action_id = presenter._connection_check_tracker.active_action.action_id

    presenter._run_check_connection(action_id)

    assert view_model.connectionResultIsError is True
    assert "NOT_CONFIGURED" in view_model.connectionResultText


def test_an_exception_from_the_dispatcher_is_reported_not_raised(
    presenter, mock_dispatcher
):
    mock_dispatcher.dispatch.side_effect = RuntimeError("boom")
    view_model = presenter._settings_view_model
    view_model.checkConnectionRequested.emit()
    action_id = presenter._connection_check_tracker.active_action.action_id

    presenter._run_check_connection(action_id)  # must not raise

    assert view_model.connectionResultIsError is True
    assert "boom" in view_model.connectionResultText


def test_a_stale_result_from_a_superseded_click_is_discarded(
    presenter, mock_dispatcher
):
    """Two clicks in a row: the first click's action_id is invalidated by
    `begin_action()` on the second — its result arriving late must not
    overwrite the second (newer) click's outcome, per
    `async-ui-action-rule.md`."""
    view_model = presenter._settings_view_model
    view_model.checkConnectionRequested.emit()
    stale_action_id = presenter._connection_check_tracker.active_action.action_id

    view_model.checkConnectionRequested.emit()  # supersedes the first
    current_action_id = presenter._connection_check_tracker.active_action.action_id
    assert current_action_id != stale_action_id

    mock_dispatcher.dispatch.return_value = _SUCCESS_STATUS
    presenter._run_check_connection(stale_action_id)  # the stale one arrives late

    # Still "checking" — the stale callback must not have unlocked the
    # button or written a result meant for the superseded click.
    assert view_model.connectionChecking is True
    assert view_model.connectionResultText == ""


# ---------------------------------------------------------------------------
# Widget rendering
# ---------------------------------------------------------------------------


def test_real_button_click_reaches_the_presenter_and_locks_the_widget(
    presenter, qapp, mock_thread_manager
):
    qapp.processEvents()
    button = presenter.view.findChild(QPushButton, "btnCheckConnection")

    button.click()
    qapp.processEvents()

    mock_thread_manager.submit.assert_called_once()
    assert button.isEnabled() is False
    assert button.text() == "Đang kiểm tra..."


def test_a_result_renders_on_the_real_label(presenter, qapp, mock_dispatcher):
    mock_dispatcher.dispatch.return_value = _SUCCESS_STATUS
    view_model = presenter._settings_view_model
    view_model.checkConnectionRequested.emit()
    action_id = presenter._connection_check_tracker.active_action.action_id

    presenter._run_check_connection(action_id)
    qapp.processEvents()

    label = presenter.view.findChild(QLabel, "lblConnectionResult")
    button = presenter.view.findChild(QPushButton, "btnCheckConnection")
    assert "FUTURES_TESTNET" in label.text()
    assert button.isEnabled() is True
    assert button.text() == "Kiểm tra kết nối"
