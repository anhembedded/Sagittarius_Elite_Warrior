"""`EPIC-021K` §2.2/§4 — the Trading screen's "DỪNG KHẨN CẤP" button.

Same construction pattern `test_trading_presenter_toggle.py` uses: the
background worker (`_run_emergency_stop`) is called directly instead of
through a real `IThreadManager` pool, so the full
begin -> emit -> ownership-check -> ViewModel-update chain runs
synchronously and for real. `view` stays a `MagicMock` for the same reason
documented there.

Deliberately does **not** patch `@safe_ui_action` onto
`_on_emergency_stop_requested` — the task's own design section (`EPIC-021K`
§2.2) forbids it for this one button, on purpose, so an exception must
reach the UI rather than vanish. `test_a_synchronous_failure_is_reported_
not_swallowed` is the guard that proves that decision is actually in the
code, not just in a comment.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.application.services.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.emergency_stop import (
    EmergencyStopCommand,
    EmergencyStopResult,
    EmergencyStopStepResult,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_presenter import (
    TradingPresenter,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

_SUCCESS = EmergencyStopStepResult(succeeded=True, detail="OK")


def _result(
    *, orders_ok: bool = True, positions_ok: bool = True
) -> EmergencyStopResult:
    return EmergencyStopResult(
        trading_disabled=_SUCCESS,
        orders_cancelled=(
            _SUCCESS if orders_ok else EmergencyStopStepResult(False, "APIError")
        ),
        positions_closed=(
            _SUCCESS
            if positions_ok
            else EmergencyStopStepResult(False, "Margin is insufficient")
        ),
    )


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get_all.return_value = {
        "DEFAULT_SYMBOLS": ["BTCUSDT"],
        "DEFAULT_INTERVAL": "1m",
    }
    config.get.side_effect = lambda key, default=None, cast=None: (
        True if key == DEV_MODE_CONFIG_KEY else default
    )
    return config


@pytest.fixture
def mock_dispatcher():
    return MagicMock()


@pytest.fixture
def mock_thread_manager():
    return MagicMock()


@pytest.fixture
def session_state():
    return TradingSessionState()


@pytest.fixture
def equity_recorder():
    return EquityCurveRecorder()


@pytest.fixture
def container(
    mock_config, mock_dispatcher, mock_thread_manager, session_state, equity_recorder
):
    c = MagicMock()

    def resolve(interface):
        if interface is IConfig:
            return mock_config
        if interface is IDispatcher:
            return mock_dispatcher
        if interface is IThreadManager:
            return mock_thread_manager
        if interface is TradingSessionState:
            return session_state
        if interface is EquityCurveRecorder:
            return equity_recorder
        return MagicMock()

    c.resolve.side_effect = resolve
    return c


@pytest.fixture
def view():
    return MagicMock()


@pytest.fixture
def presenter(qapp, view, container, mock_thread_manager):
    p = TradingPresenter(view, container)
    mock_thread_manager.submit.reset_mock()
    return p


def test_the_button_submits_the_worker(presenter, mock_thread_manager):
    presenter._view_model.emergencyStopRequested.emit()

    mock_thread_manager.submit.assert_called_once()
    submitted_callable = mock_thread_manager.submit.call_args[0][0]
    assert submitted_callable == presenter._run_emergency_stop


def test_the_worker_dispatches_the_command(presenter, mock_dispatcher):
    mock_dispatcher.dispatch.return_value = _result()

    presenter._run_emergency_stop(action_id=1)

    mock_dispatcher.dispatch.assert_called_once_with(
        EmergencyStopCommand, EmergencyStopCommand()
    )


def test_full_success_turns_trading_off_and_reports_success(presenter, mock_dispatcher):
    mock_dispatcher.dispatch.return_value = _result()
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)

    assert presenter._view_model.enabled is False
    assert presenter._view_model.toggleBusy is False
    assert presenter._view_model.statusIsError is False
    assert "Đã dừng khẩn cấp" in presenter._view_model.statusMessage


def test_partial_failure_is_reported_as_failure_not_success(presenter, mock_dispatcher):
    mock_dispatcher.dispatch.return_value = _result(positions_ok=False)
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)

    # Trading is still off (step 1 always ran and succeeded) — the danger
    # this VO exists to prevent is claiming full success, not claiming a
    # trading-disabled state that didn't happen.
    assert presenter._view_model.enabled is False
    assert presenter._view_model.statusIsError is True
    assert "THẤT BẠI MỘT PHẦN" in presenter._view_model.statusMessage


def test_an_exception_from_the_dispatcher_is_reported_not_raised(
    presenter, mock_dispatcher
):
    mock_dispatcher.dispatch.side_effect = RuntimeError("boom")
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)  # must not raise

    assert presenter._view_model.statusIsError is True
    assert "boom" in presenter._view_model.statusMessage


def test_a_stale_result_from_a_superseded_click_is_discarded(
    presenter, mock_dispatcher
):
    presenter._view_model.emergencyStopRequested.emit()
    stale_action_id = presenter._toggle_tracker.active_action.action_id

    presenter._view_model.toggleRequested.emit()  # supersedes it

    mock_dispatcher.dispatch.return_value = _result()
    presenter._run_emergency_stop(stale_action_id)  # arrives late

    assert presenter._view_model.statusMessage != "Đã dừng khẩn cấp."


def test_a_synchronous_failure_is_reported_not_swallowed(presenter, mock_dispatcher):
    """The task's own §2.2: this slot must NOT be `@safe_ui_action` — an
    exception raised before the worker is even submitted (here, forced by
    making `begin_action` itself blow up) has to reach `statusMessage` via
    this method's own `except Exception`, not vanish silently."""
    presenter._toggle_tracker.begin_action = MagicMock(side_effect=RuntimeError("boom"))

    presenter._view_model.emergencyStopRequested.emit()  # must not raise

    assert presenter._view_model.statusIsError is True
    assert "boom" in presenter._view_model.statusMessage
