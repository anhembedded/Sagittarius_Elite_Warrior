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
from datetime import UTC, datetime
from decimal import Decimal
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
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_presenter import (
    TradingPresenter,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

_SUCCESS = EmergencyStopStepResult(succeeded=True, detail="OK")


def _position(symbol: str = "BTCUSDT") -> LivePosition:
    return LivePosition(
        symbol=symbol,
        position_amt=Decimal("0.002"),
        entry_price=Decimal("64105.35"),
        mark_price=Decimal("64105.35"),
        unrealized_pnl=Decimal("-0.02"),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def _result(
    *,
    orders_ok: bool = True,
    positions_ok: bool = True,
    final_positions: tuple[LivePosition, ...] = (),
    final_open_orders: tuple = (),
    final_state_confirmed: bool = False,
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
        final_positions=final_positions,
        final_open_orders=final_open_orders,
        final_state_confirmed=final_state_confirmed,
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
    action_id = presenter._emergency_stop_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)

    assert presenter._view_model.enabled is False
    assert presenter._view_model.toggleBusy is False
    assert presenter._view_model.statusIsError is False
    assert "Đã dừng khẩn cấp" in presenter._view_model.statusMessage


def test_a_confirmed_final_state_replaces_the_stale_positions_and_open_orders(
    presenter, mock_dispatcher
):
    """`BUG-093` — before this fix, `_positions`/`_open_orders` were never
    touched by `_on_emergency_stop_completed`: the user-data stream this
    screen otherwise relies on is already stopped by Emergency Stop's own
    step 1, so nothing else would ever correct them. A confirmed final
    read must overwrite whatever was there before, even down to empty
    (the fully-successful case: everything closed)."""
    presenter._positions = {"ETHUSDT": _position("ETHUSDT")}  # stale, pre-stop state
    mock_dispatcher.dispatch.return_value = _result(
        final_positions=(), final_open_orders=(), final_state_confirmed=True
    )
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._emergency_stop_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)

    assert presenter._positions == {}
    assert presenter._open_orders == {}
    presenter.view.set_positions.assert_called_with([])
    presenter.view.set_open_orders.assert_called_with([])


def test_an_unconfirmed_final_state_leaves_stale_tables_but_warns(
    presenter, mock_dispatcher
):
    """`BUG-093` — when even the confirmation read fails, showing an
    empty table would claim "confirmed flat" for an account this app
    could not actually verify; showing the pre-stop data unchanged is
    honest about what is and isn't known, as long as it's paired with a
    visible warning (never silent staleness)."""
    stale_positions = {"ETHUSDT": _position("ETHUSDT")}
    presenter._positions = dict(stale_positions)
    mock_dispatcher.dispatch.return_value = _result(final_state_confirmed=False)
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._emergency_stop_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)

    assert presenter._positions == stale_positions
    assert any(
        "Không thể xác nhận trạng thái" in entry.message
        for entry in presenter._view_model.log_model.entries
    )


def test_partial_failure_is_reported_as_failure_not_success(presenter, mock_dispatcher):
    mock_dispatcher.dispatch.return_value = _result(positions_ok=False)
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._emergency_stop_tracker.active_action.action_id

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
    action_id = presenter._emergency_stop_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)  # must not raise

    assert presenter._view_model.statusIsError is True
    assert "boom" in presenter._view_model.statusMessage


def test_a_stale_result_from_a_superseded_emergency_stop_action_is_discarded(
    presenter, mock_dispatcher
):
    """`BUG-089` narrowed what can supersede an in-flight Emergency Stop
    action to another action on its *own* tracker — a toggle click can no
    longer do it (see `test_a_toggle_click_while_emergency_stop_is_pending_
    is_refused_not_superseding_it` below). The tracker's own stale-id
    fencing still has to work, so it's driven directly here rather than
    through a click path the presenter itself now blocks."""
    presenter._view_model.emergencyStopRequested.emit()
    stale_action_id = presenter._emergency_stop_tracker.active_action.action_id

    presenter._emergency_stop_tracker.begin_action(
        "emergency_stop", None, None
    )  # a second action superseding the first, bypassing the UI debounce

    mock_dispatcher.dispatch.return_value = _result()
    presenter._run_emergency_stop(stale_action_id)  # arrives late

    assert presenter._view_model.statusMessage != "Đã dừng khẩn cấp."


def test_a_toggle_click_while_emergency_stop_is_pending_is_refused_not_superseding_it(
    presenter, mock_dispatcher, mock_thread_manager
):
    """`BUG-089` — before this fix, `_toggle_tracker` was shared with
    Emergency Stop, so this exact click sequence fenced Emergency Stop's
    own in-flight action as stale and its real result (including a
    partial-failure warning) was silently dropped by
    `_on_emergency_stop_completed`'s ownership check."""
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._emergency_stop_tracker.active_action.action_id
    mock_thread_manager.submit.reset_mock()

    presenter._view_model.toggleRequested.emit()  # must not supersede it

    mock_thread_manager.submit.assert_not_called()  # no enable/disable worker submitted
    assert presenter._view_model.toggleBusy is True  # button stayed disabled

    mock_dispatcher.dispatch.return_value = _result()
    presenter._run_emergency_stop(action_id)  # the original action, still current

    assert presenter._view_model.statusIsError is False
    assert "Đã dừng khẩn cấp" in presenter._view_model.statusMessage


def test_a_second_emergency_stop_click_while_one_is_pending_is_refused(
    presenter, mock_thread_manager
):
    """`BUG-089` debounce — the button itself is never disabled, so a
    double-click (or an impatient second press) must not submit a second,
    independent `EmergencyStopCommand` racing the first one's own
    cancel/close calls against the live exchange."""
    presenter._view_model.emergencyStopRequested.emit()
    mock_thread_manager.submit.reset_mock()

    presenter._view_model.emergencyStopRequested.emit()

    mock_thread_manager.submit.assert_not_called()


def test_a_synchronous_failure_is_reported_not_swallowed(presenter, mock_dispatcher):
    """The task's own §2.2: this slot must NOT be `@safe_ui_action` — an
    exception raised before the worker is even submitted (here, forced by
    making `begin_action` itself blow up) has to reach `statusMessage` via
    this method's own `except Exception`, not vanish silently."""
    presenter._emergency_stop_tracker.begin_action = MagicMock(
        side_effect=RuntimeError("boom")
    )

    presenter._view_model.emergencyStopRequested.emit()  # must not raise

    assert presenter._view_model.statusIsError is True
    assert "boom" in presenter._view_model.statusMessage
