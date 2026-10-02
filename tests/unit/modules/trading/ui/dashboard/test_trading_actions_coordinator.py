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
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.manual_order_intent import (
    ManualOrderDirection,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.coordinators.trading_actions_coordinator import (
    CompletionEmitters,
    TradingActionsCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)

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
def order_submission() -> FakeOrderSubmission:
    return FakeOrderSubmission()


@pytest.fixture
def account() -> FakeAccountSnapshot:
    return FakeAccountSnapshot()


@pytest.fixture
def market_type() -> MarketType:
    """`FUTURES_USD_M` — the venue every other fixture in this file already
    assumes (`_live_position()`'s own leveraged shape); Spot-specific
    behaviour gets its own dedicated fixture override below."""
    return MarketType.FUTURES_USD_M


@pytest.fixture
def manual_order_tracker() -> ActionOwnershipTracker:
    return ActionOwnershipTracker()


@pytest.fixture
def append_log() -> _Recorder:
    return _Recorder()


@pytest.fixture
def set_manual_order_state() -> _Recorder:
    return _Recorder()


@pytest.fixture
def emit_manual_order_completed() -> _Recorder:
    return _Recorder()


@pytest.fixture
def emit_cancel_order_completed() -> _Recorder:
    return _Recorder()


def _build_coordinator(
    *,
    thread_manager,
    order_submission,
    account,
    market_type,
    manual_order_tracker,
    append_log,
    set_manual_order_state,
    get_last_price,
    emit_manual_order_completed,
    emit_cancel_order_completed,
) -> TradingActionsCoordinator:
    """Shared construction for the default fixture and the one test that
    needs a non-default `get_last_price` — keeps the grouping into
    `CompletionEmitters` (`code/quality.md` §7) written in
    exactly one place."""
    return TradingActionsCoordinator(
        thread_manager=thread_manager,
        order_submission=order_submission,
        account=account,
        market_type=market_type,
        manual_order_tracker=manual_order_tracker,
        manual_order_action_kind=_MANUAL_ORDER,
        completion_emitters=CompletionEmitters(
            manual_order=emit_manual_order_completed,
            cancel_order=emit_cancel_order_completed,
        ),
        set_manual_order_state=set_manual_order_state,
        append_log=append_log,
        get_active_symbol=lambda: "BTCUSDT",
        get_last_price=get_last_price,
    )


@pytest.fixture
def coordinator(
    thread_manager,
    order_submission,
    account,
    market_type,
    manual_order_tracker,
    append_log,
    set_manual_order_state,
    emit_manual_order_completed,
    emit_cancel_order_completed,
) -> TradingActionsCoordinator:
    return _build_coordinator(
        thread_manager=thread_manager,
        order_submission=order_submission,
        account=account,
        market_type=market_type,
        manual_order_tracker=manual_order_tracker,
        append_log=append_log,
        set_manual_order_state=set_manual_order_state,
        get_last_price=lambda _symbol: Decimal(64000),
        emit_manual_order_completed=emit_manual_order_completed,
        emit_cancel_order_completed=emit_cancel_order_completed,
    )


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
    order_submission,
    account,
    market_type,
    manual_order_tracker,
    append_log,
    set_manual_order_state,
    emit_manual_order_completed,
    emit_cancel_order_completed,
):
    coordinator = _build_coordinator(
        thread_manager=thread_manager,
        order_submission=order_submission,
        account=account,
        market_type=market_type,
        manual_order_tracker=manual_order_tracker,
        append_log=append_log,
        set_manual_order_state=set_manual_order_state,
        get_last_price=lambda _symbol: None,  # no live data yet
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


def test_run_manual_order_refuses_a_short_click_on_spot_without_submitting(
    thread_manager,
    order_submission,
    account,
    manual_order_tracker,
    append_log,
    set_manual_order_state,
    emit_manual_order_completed,
    emit_cancel_order_completed,
):
    """`EPIC-027K` post-review fix (PR #284) — before this fix, a Spot
    Short click reached `order_submission.submit()` as a plain
    `SELL`/`reduce_only=False`, indistinguishable from a deliberate sale of
    a real holding, because `SpotTradingClient.get_positions()` always
    answers `[]` so `current_position` is always `None`. The coordinator's
    own `market_type` must refuse it before any order is built."""
    coordinator = _build_coordinator(
        thread_manager=thread_manager,
        order_submission=order_submission,
        account=account,
        market_type=MarketType.SPOT,
        manual_order_tracker=manual_order_tracker,
        append_log=append_log,
        set_manual_order_state=set_manual_order_state,
        get_last_price=lambda _symbol: Decimal(64000),
        emit_manual_order_completed=emit_manual_order_completed,
        emit_cancel_order_completed=emit_cancel_order_completed,
    )

    coordinator.run_manual_order(
        3,
        "BTCUSDT",
        ManualOrderDirection.SHORT,
        Decimal("0.01"),
        OrderType.MARKET,
        Decimal(64000),
    )

    assert order_submission.submitted_live == []
    assert order_submission.submitted_dry == []
    (call,) = emit_manual_order_completed.calls
    action_id, result, error = call[0]
    assert action_id == 3
    assert result is None
    assert "Short is not supported on Spot" in error


def test_run_manual_order_sells_a_real_spot_holding(
    thread_manager,
    order_submission,
    account,
    manual_order_tracker,
    append_log,
    set_manual_order_state,
    emit_manual_order_completed,
    emit_cancel_order_completed,
):
    """`EPIC-027O` — the Sell counterpart to the refusal above: once a real,
    freshly-read holding backs the click, it goes through as a plain
    `SELL`/`reduce_only=False` (Spot's `create_order` rejects `reduceOnly`
    outright — `manual_order_intent_for()`'s own docstring)."""
    coordinator = _build_coordinator(
        thread_manager=thread_manager,
        order_submission=order_submission,
        account=account,
        market_type=MarketType.SPOT,
        manual_order_tracker=manual_order_tracker,
        append_log=append_log,
        set_manual_order_state=set_manual_order_state,
        get_last_price=lambda _symbol: Decimal(64000),
        emit_manual_order_completed=emit_manual_order_completed,
        emit_cancel_order_completed=emit_cancel_order_completed,
    )
    account.answer_with(
        ExchangeConnectionStatus(
            venue=TradingVenue.SPOT_TESTNET,
            reachable=True,
            failure=None,
            server_time_skew_ms=0,
            usdt_balance=Decimal(1000),
            position_mode=None,
            margin_type=None,
            open_position_count=None,
            holdings=(
                SpotHolding(
                    asset="BTC",
                    free=Decimal("0.5"),
                    locked=Decimal(0),
                    dust_threshold=Decimal("0.00001"),
                ),
            ),
        )
    )
    order_submission.submit_answers(
        ExecuteOrderResult(
            blocked_by=None, preview=None, limit_checks=(), submitted_order=None
        )
    )

    coordinator.run_manual_order(
        4,
        "BTCUSDT",
        ManualOrderDirection.SHORT,
        Decimal("0.01"),
        OrderType.MARKET,
        Decimal(64000),
    )

    (request,) = order_submission.submitted_live
    assert request.side is OrderSide.SELL
    assert request.reduce_only is False
    (call,) = emit_manual_order_completed.calls
    action_id, result, error = call[0]
    assert action_id == 4
    assert error is None
    assert result.blocked_by is None


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
