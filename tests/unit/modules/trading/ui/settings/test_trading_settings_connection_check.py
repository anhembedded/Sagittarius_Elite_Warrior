"""`EPIC-021D` — Trading settings section's "Check Connection" button.

Moved wholesale off
`tests/unit/presentation/ui/screens/test_settings_presenter_connection_check.py`
(`EPIC-025E` PR 4.4e) — this coverage was entirely trading's own concern
(`IAccountSnapshot`/`ITradingSession`); only the class names and import
paths changed.

Calls `TradingSettingsPresenter._run_check_connection()` directly rather than
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
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
    config.get.side_effect = lambda key, default=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )
    return config


@pytest.fixture
def account() -> FakeAccountSnapshot:
    """`EPIC-025` PR 1.3b — `IAccountSnapshot`'s verified fake, in place
    of a mocked dispatcher.

    The tests below used to assert
    `dispatch.assert_called_once_with(GetExchangeConnectionStatusQuery, ...)`,
    which proved that a private call happened and nothing about what the
    user sees (`domain-truth-rule.md`, and `pr-review` E2). The fake lets
    each one assert the effect instead — what the label renders — and
    `connection_checks` covers the one case where "was it asked at all" is
    genuinely the question."""
    return FakeAccountSnapshot()


@pytest.fixture
def mock_thread_manager():
    return Mock()


@pytest.fixture
def credentials_provider(tmp_path):
    return EnvFirstCredentialsProvider(SecretsFileSource(str(tmp_path / "s.json")))


@pytest.fixture
def session_state() -> FakeTradingSession:
    """`BOT-125` — a real answer so `_venue_locked()` reads a real bool.

    `EPIC-025` PR 1.3b: the port's verified fake. Starts disabled, which is
    what a fresh session guarantees (`EPIC-021G` §2.3); a `Mock` would hand
    back a truthy attribute and lock the venue combo in every test."""
    return FakeTradingSession()


@pytest.fixture
def container(
    mock_config,
    account,
    mock_thread_manager,
    credentials_provider,
    session_state,
):
    from sagittarius_engine.interfaces import IConfig

    c = Mock()

    def resolve(interface):
        if interface is IConfig:
            return mock_config
        if interface is IThreadManager:
            return mock_thread_manager
        if interface is IExchangeCredentialsProvider:
            return credentials_provider
        if interface is ITradingSession:
            return session_state
        if interface is IAccountSnapshot:
            return account
        return Mock()

    c.resolve.side_effect = resolve
    return c


@pytest.fixture
def presenter(qapp, container, request):
    view = TradingSettingsView()
    view.resize(1200, 800)
    request.addfinalizer(view.deleteLater)
    return TradingSettingsPresenter(view, container)


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
    presenter, account
):
    account.answer_with(_SUCCESS_STATUS)
    view_model = presenter._settings_view_model
    view_model.checkConnectionRequested.emit()
    action_id = presenter._connection_check_tracker.active_action.action_id

    presenter._run_check_connection(action_id)

    # The port was asked exactly once — a screen that re-checked on every
    # repaint would be a real network round trip per frame.
    assert account.connection_checks == 1
    assert view_model.connectionChecking is False
    assert "FUTURES_TESTNET" in view_model.connectionResultText
    assert view_model.connectionResultIsError is False


def test_a_failed_status_renders_as_an_error(presenter, account):
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
    account.answer_with(failed_status)
    view_model = presenter._settings_view_model
    view_model.checkConnectionRequested.emit()
    action_id = presenter._connection_check_tracker.active_action.action_id

    presenter._run_check_connection(action_id)

    assert view_model.connectionResultIsError is True
    assert "NOT_CONFIGURED" in view_model.connectionResultText


def test_an_exception_from_the_port_is_reported_not_raised(presenter, account):
    # `IAccountSnapshot.check_connection()` promises never to raise, and the
    # fake keeps that promise — so the failure is injected the only way a
    # real one could reach here: the adapter behind the port breaking its
    # own contract. The Presenter's worker boundary must still report it
    # rather than lose it to a background-thread traceback (`BUG-031`).
    account.check_connection = Mock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]
    view_model = presenter._settings_view_model
    view_model.checkConnectionRequested.emit()
    action_id = presenter._connection_check_tracker.active_action.action_id

    presenter._run_check_connection(action_id)  # must not raise

    assert view_model.connectionResultIsError is True
    assert "boom" in view_model.connectionResultText


def test_a_stale_result_from_a_superseded_click_is_discarded(presenter, account):
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

    account.answer_with(_SUCCESS_STATUS)
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
    assert button.text() == "Checking..."


def test_a_result_renders_on_the_real_label(presenter, qapp, account):
    account.answer_with(_SUCCESS_STATUS)
    view_model = presenter._settings_view_model
    view_model.checkConnectionRequested.emit()
    action_id = presenter._connection_check_tracker.active_action.action_id

    presenter._run_check_connection(action_id)
    qapp.processEvents()

    label = presenter.view.findChild(QLabel, "lblConnectionResult")
    button = presenter.view.findChild(QPushButton, "btnCheckConnection")
    assert "FUTURES_TESTNET" in label.text()
    assert button.isEnabled() is True
    assert button.text() == "Check Connection"
