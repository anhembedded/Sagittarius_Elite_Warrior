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

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
    EmergencyStopStepResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)

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


def test_the_button_submits_the_worker(presenter, mock_thread_manager):
    presenter._view_model.emergencyStopRequested.emit()

    mock_thread_manager.submit.assert_called_once()
    submitted_callable = mock_thread_manager.submit.call_args[0][0]
    assert submitted_callable == presenter._run_emergency_stop


def test_the_worker_calls_the_session_port_once(presenter, trading_session):
    trading_session.emergency_stop_answers(_result())

    presenter._run_emergency_stop(action_id=1)

    assert trading_session.emergency_stops == 1


def test_full_success_turns_trading_off_and_reports_success(presenter, trading_session):
    trading_session.emergency_stop_answers(_result())
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._emergency_stop_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)

    assert presenter._view_model.enabled is False
    assert presenter._view_model.toggleBusy is False
    assert presenter._view_model.statusIsError is False
    assert "Emergency stop completed" in presenter._view_model.statusMessage


def test_a_confirmed_final_state_replaces_the_stale_positions_and_open_orders(
    presenter, trading_session
):
    """`BUG-093` — before this fix, `_positions`/`_open_orders` were never
    touched by `_on_emergency_stop_completed`: the user-data stream this
    screen otherwise relies on is already stopped by Emergency Stop's own
    step 1, so nothing else would ever correct them. A confirmed final
    read must overwrite whatever was there before, even down to empty
    (the fully-successful case: everything closed)."""
    # stale, pre-stop state
    presenter._order_book.on_position_changed(_position("ETHUSDT"))
    trading_session.emergency_stop_answers(
        _result(final_positions=(), final_open_orders=(), final_state_confirmed=True)
    )
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._emergency_stop_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)

    presenter.view.set_positions.assert_called_with([])
    presenter.view.set_open_orders.assert_called_with([])


def test_an_unconfirmed_final_state_leaves_stale_tables_but_warns(
    presenter, trading_session
):
    """`BUG-093` — when even the confirmation read fails, showing an
    empty table would claim "confirmed flat" for an account this app
    could not actually verify; showing the pre-stop data unchanged is
    honest about what is and isn't known, as long as it's paired with a
    visible warning (never silent staleness)."""
    stale_position = _position("ETHUSDT")
    presenter._order_book.on_position_changed(stale_position)
    presenter.view.set_positions.reset_mock()
    trading_session.emergency_stop_answers(_result(final_state_confirmed=False))
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._emergency_stop_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)

    # Never re-rendered — the early return in `_apply_emergency_stop_final_state`
    # leaves whatever was there before untouched, exactly what "stale" means.
    presenter.view.set_positions.assert_not_called()
    assert any(
        "Could not confirm account state" in entry.message
        for entry in presenter._view_model.log_model.entries
    )


def test_partial_failure_is_reported_as_failure_not_success(presenter, trading_session):
    trading_session.emergency_stop_answers(_result(positions_ok=False))
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._emergency_stop_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)

    # Trading is still off (step 1 always ran and succeeded) — the danger
    # this VO exists to prevent is claiming full success, not claiming a
    # trading-disabled state that didn't happen.
    assert presenter._view_model.enabled is False
    assert presenter._view_model.statusIsError is True
    assert "PARTIALLY FAILED" in presenter._view_model.statusMessage


def test_an_exception_from_the_session_port_is_reported_not_raised(
    presenter, trading_session
):
    trading_session.emergency_stop_raises(RuntimeError("boom"))
    presenter._view_model.emergencyStopRequested.emit()
    action_id = presenter._emergency_stop_tracker.active_action.action_id

    presenter._run_emergency_stop(action_id)  # must not raise

    assert presenter._view_model.statusIsError is True
    assert "boom" in presenter._view_model.statusMessage


def test_a_stale_result_from_a_superseded_emergency_stop_action_is_discarded(
    presenter, trading_session
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

    trading_session.emergency_stop_answers(_result())
    presenter._run_emergency_stop(stale_action_id)  # arrives late

    assert presenter._view_model.statusMessage != "Emergency stop completed."


def test_a_toggle_click_while_emergency_stop_is_pending_is_refused_not_superseding_it(
    presenter, trading_session, mock_thread_manager
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

    trading_session.emergency_stop_answers(_result())
    presenter._run_emergency_stop(action_id)  # the original action, still current

    assert presenter._view_model.statusIsError is False
    assert "Emergency stop completed" in presenter._view_model.statusMessage


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


def test_a_synchronous_failure_is_reported_not_swallowed(presenter, trading_session):
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
