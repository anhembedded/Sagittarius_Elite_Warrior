"""`BOT-144` — direct, isolated unit tests for `TradingActionsCoordinator`,
extracted from `DashboardPresenter` to keep that file closer to the
400-line ceiling.

The exhaustive behavioral matrix (reconciling tables, log wording, FSM/UI
side effects on completion) already lives in `test_dashboard_presenter.py`,
exercised through the real `DashboardPresenter`/`presenter._trading_actions`
composition; these tests instead prove the coordinator's own `request_*`/
`run_*` orchestration works standalone, against the module's real verified
fakes and a real `ActionOwnershipTracker` — the same shape
`test_strategy_arming_coordinator.py` already uses for its own sibling
Coordinator.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
    EmergencyStopStepResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.coordinators.trading_actions_coordinator import (
    TradingActionsCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)

_TOGGLE = "toggle_trading"
_EMERGENCY_STOP = "emergency_stop"
_MANUAL_ORDER = "manual_order"


def _live_position(symbol: str, signed_amount: str) -> LivePosition:
    return LivePosition(
        symbol=symbol,
        position_amt=Decimal(signed_amount),
        entry_price=Decimal(64000),
        mark_price=Decimal(64000),
        unrealized_pnl=Decimal(0),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=None,
    )


class _Recorder:
    """A callable that remembers every call it received — the shape
    `testing-rule.md` asks for over a bare `Mock` when the test also needs
    to read back *what* was passed, not just that something was."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, *args):
        self.calls.append(args)


@pytest.fixture
def thread_manager() -> MagicMock:
    """`IThreadManager` is the shared engine kernel port, mocked the same
    way `test_dashboard_presenter.py`'s own `mock_thread_mgr` fixture does —
    submissions are asserted by identity/args, never actually dispatched."""
    return MagicMock()


@pytest.fixture
def trading_session() -> FakeTradingSession:
    return FakeTradingSession()


@pytest.fixture
def order_submission() -> FakeOrderSubmission:
    return FakeOrderSubmission()


@pytest.fixture
def account() -> FakeAccountSnapshot:
    return FakeAccountSnapshot()


@pytest.fixture
def toggle_tracker() -> ActionOwnershipTracker:
    return ActionOwnershipTracker()


@pytest.fixture
def emergency_stop_tracker() -> ActionOwnershipTracker:
    return ActionOwnershipTracker()


@pytest.fixture
def manual_order_tracker() -> ActionOwnershipTracker:
    return ActionOwnershipTracker()


@pytest.fixture
def append_log() -> _Recorder:
    return _Recorder()


@pytest.fixture
def set_trading_state() -> _Recorder:
    return _Recorder()


@pytest.fixture
def set_manual_order_state() -> _Recorder:
    return _Recorder()


@pytest.fixture
def emit_enable_completed() -> _Recorder:
    return _Recorder()


@pytest.fixture
def emit_disable_completed() -> _Recorder:
    return _Recorder()


@pytest.fixture
def emit_emergency_stop_completed() -> _Recorder:
    return _Recorder()


@pytest.fixture
def emit_manual_order_completed() -> _Recorder:
    return _Recorder()


@pytest.fixture
def emit_cancel_order_completed() -> _Recorder:
    return _Recorder()


@pytest.fixture
def coordinator(
    thread_manager,
    trading_session,
    order_submission,
    account,
    toggle_tracker,
    emergency_stop_tracker,
    manual_order_tracker,
    append_log,
    set_trading_state,
    set_manual_order_state,
    emit_enable_completed,
    emit_disable_completed,
    emit_emergency_stop_completed,
    emit_manual_order_completed,
    emit_cancel_order_completed,
) -> TradingActionsCoordinator:
    return TradingActionsCoordinator(
        thread_manager=thread_manager,
        trading_session=trading_session,
        order_submission=order_submission,
        account=account,
        toggle_tracker=toggle_tracker,
        emergency_stop_tracker=emergency_stop_tracker,
        manual_order_tracker=manual_order_tracker,
        toggle_action_kind=_TOGGLE,
        emergency_stop_action_kind=_EMERGENCY_STOP,
        manual_order_action_kind=_MANUAL_ORDER,
        set_trading_state=set_trading_state,
        set_manual_order_state=set_manual_order_state,
        append_log=append_log,
        get_active_symbol=lambda: "BTCUSDT",
        get_last_price=lambda _symbol: Decimal(64000),
        emit_enable_completed=emit_enable_completed,
        emit_disable_completed=emit_disable_completed,
        emit_emergency_stop_completed=emit_emergency_stop_completed,
        emit_manual_order_completed=emit_manual_order_completed,
        emit_cancel_order_completed=emit_cancel_order_completed,
    )


# ---------------------------------------------------------------------------
# Enable/Disable toggle
# ---------------------------------------------------------------------------


def test_request_toggle_when_disabled_submits_enable(coordinator, thread_manager):
    coordinator.request_toggle()

    thread_manager.submit.assert_called_once()
    submitted_callable, action_id = thread_manager.submit.call_args[0]
    assert submitted_callable == coordinator.run_enable
    assert isinstance(action_id, int)


def test_request_toggle_when_enabled_submits_disable(
    coordinator, thread_manager, trading_session
):
    trading_session.set_enabled(enabled=True)

    coordinator.request_toggle()

    thread_manager.submit.assert_called_once()
    submitted_callable = thread_manager.submit.call_args[0][0]
    assert submitted_callable == coordinator.run_disable


def test_request_toggle_is_blocked_while_emergency_stop_is_pending(
    coordinator, thread_manager, emergency_stop_tracker
):
    """`BUG-089`'s precedent — a toggle click must never race an Emergency
    Stop already in flight."""
    emergency_stop_tracker.begin_action(_EMERGENCY_STOP, None, None)

    coordinator.request_toggle()

    thread_manager.submit.assert_not_called()
    assert emergency_stop_tracker.active_outcome is ActionOutcome.PENDING


def test_run_enable_reports_success(
    coordinator, trading_session, emit_enable_completed
):
    trading_session.enable_answers(
        EnableTradingResult(
            enabled=True,
            block_reason=None,
            reconciled_positions=(),
            reconciled_open_orders=(),
        )
    )

    coordinator.run_enable(7)

    assert trading_session.enables == 1
    (call,) = emit_enable_completed.calls
    action_id, result, error = call[0]
    assert action_id == 7
    assert result.enabled is True
    assert error is None


def test_run_enable_reports_an_exception_rather_than_raising(
    coordinator, trading_session, emit_enable_completed
):
    trading_session.enable_raises(RuntimeError("boom"))

    coordinator.run_enable(3)  # must not raise

    (call,) = emit_enable_completed.calls
    action_id, result, error = call[0]
    assert action_id == 3
    assert result is None
    assert error == "boom"


def test_run_disable_reports_completion(
    coordinator, trading_session, emit_disable_completed
):
    coordinator.run_disable(5)

    assert trading_session.disables == 1
    (call,) = emit_disable_completed.calls
    action_id, error = call[0]
    assert action_id == 5
    assert error is None


# ---------------------------------------------------------------------------
# Emergency Stop
# ---------------------------------------------------------------------------


def test_request_emergency_stop_submits_the_worker_and_locks_the_toggle(
    coordinator, thread_manager, set_trading_state
):
    coordinator.request_emergency_stop()

    thread_manager.submit.assert_called_once()
    submitted_callable = thread_manager.submit.call_args[0][0]
    assert submitted_callable == coordinator.run_emergency_stop
    assert set_trading_state.calls[-1] == (False, True)  # (enabled, busy)


def test_request_emergency_stop_is_blocked_while_one_is_already_pending(
    coordinator, thread_manager, emergency_stop_tracker, append_log
):
    emergency_stop_tracker.begin_action(_EMERGENCY_STOP, None, None)

    coordinator.request_emergency_stop()

    thread_manager.submit.assert_not_called()
    assert any("already been sent" in call[0] for call in append_log.calls)


def test_request_emergency_stop_reports_a_session_exception_and_unlocks(
    coordinator, thread_manager, trading_session, set_trading_state, append_log
):
    """Deliberately not `@safe_ui_action`-shaped: a failure here must be
    seen, not swallowed — see this coordinator's own module docstring."""

    def _raise_on_submit(*_args, **_kwargs):
        raise RuntimeError("network down")

    thread_manager.submit.side_effect = _raise_on_submit

    coordinator.request_emergency_stop()

    assert any("network down" in call[0] for call in append_log.calls)
    # Unlocked again after the failure — never left stuck busy.
    assert set_trading_state.calls[-1] == (False, False)


def test_run_emergency_stop_reports_success(
    coordinator, trading_session, emit_emergency_stop_completed
):
    ok = EmergencyStopStepResult(succeeded=True, detail="OK")
    result = EmergencyStopResult(
        trading_disabled=ok,
        orders_cancelled=ok,
        positions_closed=ok,
        final_positions=(),
        final_open_orders=(),
        final_state_confirmed=True,
    )
    trading_session.emergency_stop_answers(result)

    coordinator.run_emergency_stop(9)

    assert trading_session.emergency_stops == 1
    (call,) = emit_emergency_stop_completed.calls
    action_id, returned_result, error = call[0]
    assert action_id == 9
    assert returned_result is result
    assert error is None


def test_run_emergency_stop_reports_an_exception_rather_than_raising(
    coordinator, trading_session, emit_emergency_stop_completed
):
    trading_session.emergency_stop_raises(RuntimeError("timeout"))

    coordinator.run_emergency_stop(4)  # must not raise

    (call,) = emit_emergency_stop_completed.calls
    action_id, result, error = call[0]
    assert action_id == 4
    assert result is None
    assert error == "timeout"


# ---------------------------------------------------------------------------
# Manual order (`EPIC-024B`)
# ---------------------------------------------------------------------------


def test_request_manual_order_rejects_an_invalid_direction_or_type(
    coordinator, thread_manager, append_log
):
    coordinator.request_manual_order("SIDEWAYS", 0.01, "MARKET", 0.0)

    thread_manager.submit.assert_not_called()
    assert any("Invalid manual order" in call[0] for call in append_log.calls)


def test_request_manual_order_rejects_a_non_positive_quantity(
    coordinator, thread_manager, append_log
):
    coordinator.request_manual_order("LONG", 0.0, "MARKET", 0.0)

    thread_manager.submit.assert_not_called()
    assert any("greater than 0" in call[0] for call in append_log.calls)


def test_request_manual_order_rejects_a_non_positive_limit_price(
    coordinator, thread_manager, append_log
):
    coordinator.request_manual_order("LONG", 0.01, "LIMIT", 0.0)

    thread_manager.submit.assert_not_called()
    assert any("Limit order price" in call[0] for call in append_log.calls)


def test_request_manual_order_rejects_a_market_order_with_no_known_price(
    thread_manager,
    trading_session,
    order_submission,
    account,
    toggle_tracker,
    emergency_stop_tracker,
    manual_order_tracker,
    append_log,
    set_trading_state,
    set_manual_order_state,
    emit_enable_completed,
    emit_disable_completed,
    emit_emergency_stop_completed,
    emit_manual_order_completed,
    emit_cancel_order_completed,
):
    coordinator = TradingActionsCoordinator(
        thread_manager=thread_manager,
        trading_session=trading_session,
        order_submission=order_submission,
        account=account,
        toggle_tracker=toggle_tracker,
        emergency_stop_tracker=emergency_stop_tracker,
        manual_order_tracker=manual_order_tracker,
        toggle_action_kind=_TOGGLE,
        emergency_stop_action_kind=_EMERGENCY_STOP,
        manual_order_action_kind=_MANUAL_ORDER,
        set_trading_state=set_trading_state,
        set_manual_order_state=set_manual_order_state,
        append_log=append_log,
        get_active_symbol=lambda: "BTCUSDT",
        get_last_price=lambda _symbol: None,  # no live data yet
        emit_enable_completed=emit_enable_completed,
        emit_disable_completed=emit_disable_completed,
        emit_emergency_stop_completed=emit_emergency_stop_completed,
        emit_manual_order_completed=emit_manual_order_completed,
        emit_cancel_order_completed=emit_cancel_order_completed,
    )

    coordinator.request_manual_order("LONG", 0.01, "MARKET", 0.0)

    thread_manager.submit.assert_not_called()
    assert any("market price" in call[0] for call in append_log.calls)


def test_request_manual_order_is_blocked_while_already_pending(
    coordinator, thread_manager, manual_order_tracker
):
    manual_order_tracker.begin_action(_MANUAL_ORDER, None, None)

    coordinator.request_manual_order("LONG", 0.01, "MARKET", 0.0)

    thread_manager.submit.assert_not_called()


def test_request_manual_order_submits_a_market_order_with_the_last_price(
    coordinator, thread_manager, set_manual_order_state
):
    coordinator.request_manual_order("LONG", 0.01, "MARKET", 0.0)

    thread_manager.submit.assert_called_once()
    args = thread_manager.submit.call_args[0]
    assert args[0] == coordinator.run_manual_order
    assert args[2] == "BTCUSDT"
    assert args[3] is ManualOrderDirection.LONG
    assert args[4] == Decimal("0.01")
    assert args[5] is OrderType.MARKET
    assert args[6] == Decimal(64000)  # the injected get_last_price() callback
    assert set_manual_order_state.calls[-1] == (True, "Sending order...")


def test_request_manual_order_submits_a_limit_order_with_its_own_price(
    coordinator, thread_manager
):
    coordinator.request_manual_order("SHORT", 0.02, "LIMIT", 70_000.0)

    args = thread_manager.submit.call_args[0]
    assert args[3] is ManualOrderDirection.SHORT
    assert args[4] == Decimal("0.02")
    assert args[5] is OrderType.LIMIT
    assert args[6] == Decimal("70000.0")


def test_run_manual_order_submits_one_live_order_with_the_mapped_intent(
    coordinator, account, order_submission, emit_manual_order_completed
):
    # Currently SHORT + a Long click -> BUY, reduce_only=True (closes the
    # short) — `manual_order_intent_for()`'s own table, row 2.
    account.holding([_live_position("BTCUSDT", "-0.01")])
    order_submission.submit_answers(
        ExecuteOrderResult(
            blocked_by=None, preview=None, limit_checks=(), submitted_order=None
        )
    )

    coordinator.run_manual_order(
        1,
        "BTCUSDT",
        ManualOrderDirection.LONG,
        Decimal("0.01"),
        OrderType.MARKET,
        Decimal(64000),
    )

    (request,) = order_submission.submitted_live
    assert order_submission.submitted_dry == []
    assert request.symbol == "BTCUSDT"
    assert request.side is OrderSide.BUY
    assert request.reduce_only is True
    # Read once, fresh, per attempt — never remembered from a prior click.
    assert account.position_reads == 1
    (call,) = emit_manual_order_completed.calls
    action_id, result, error = call[0]
    assert action_id == 1
    assert result.blocked_by is None
    assert error is None


def test_run_manual_order_reports_an_exception_rather_than_raising(
    coordinator, order_submission, emit_manual_order_completed
):
    order_submission.submit_raises(RuntimeError("rejected"))

    coordinator.run_manual_order(
        2,
        "BTCUSDT",
        ManualOrderDirection.LONG,
        Decimal("0.01"),
        OrderType.MARKET,
        Decimal(64000),
    )

    (call,) = emit_manual_order_completed.calls
    action_id, result, error = call[0]
    assert action_id == 2
    assert result is None
    assert error == "rejected"


# ---------------------------------------------------------------------------
# Per-order cancel (`EPIC-024B` §0)
# ---------------------------------------------------------------------------


def test_request_cancel_order_submits_the_background_worker(
    coordinator, thread_manager
):
    coordinator.request_cancel_order("BTCUSDT", "abc123")

    thread_manager.submit.assert_called_once_with(
        coordinator.run_cancel_order, "BTCUSDT", "abc123"
    )


def test_run_cancel_order_cancels_exactly_that_order_and_nothing_else(
    coordinator, order_submission, emit_cancel_order_completed
):
    order_submission.cancel_answers(CancelOrderResult(None, None))

    coordinator.run_cancel_order("BTCUSDT", "abc123")

    assert order_submission.cancelled == [("BTCUSDT", "abc123")]
    # Cancelling one order must never submit one, which the port's fake can
    # say and a bare `Mock` could not.
    assert order_submission.submitted_live == []
    (call,) = emit_cancel_order_completed.calls
    symbol, client_order_id, result, error = call[0]
    assert (symbol, client_order_id) == ("BTCUSDT", "abc123")
    assert result is not None
    assert error is None


def test_run_cancel_order_reports_an_exception_rather_than_raising(
    coordinator, order_submission, emit_cancel_order_completed
):
    """`FakeOrderSubmission.cancel()` has no answer configured (its own
    unconfigured-call guard) — the coordinator must report that failure
    through the completion callback, not let it escape the worker thread."""
    coordinator.run_cancel_order("BTCUSDT", "abc123")

    (call,) = emit_cancel_order_completed.calls
    symbol, client_order_id, result, error = call[0]
    assert (symbol, client_order_id) == ("BTCUSDT", "abc123")
    assert result is None
    assert "cancel_answers" in error
