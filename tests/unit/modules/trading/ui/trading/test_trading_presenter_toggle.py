"""`EPIC-021I` — the Trading screen's Enable/Disable toggle. What its
`OrderFeed` does to the two live tables and the chart's fill markers is
`test_trading_presenter_order_feed.py` (split off for the 400-line ceiling).

Same pattern `test_settings_presenter_connection_check.py` uses for its
own async action: background worker methods (`_run_enable`/`_run_disable`)
are called directly rather than through a real `IThreadManager` pool, so
`Signal.emit()` invokes connected slots synchronously and the full
begin -> emit -> ownership-check -> ViewModel-update chain is exercised
for real.

`view` is a `MagicMock` here (not a real `TradingView`) — `TradingPresenter`
never does `hasattr`/`getattr` capability probing on it (unlike the FSM/UI
matrix duck-typing `test_dashboard_presenter.py` warns about), and the
real View's own construction is already exercised by
`test_trading_view_contract.py`. The session is `FakeTradingSession`, the
verified fake for `ITradingSession` (`EPIC-025` PR 1.3c-1) — so a test says
what the session looks like and reads back what the screen asked it, instead
of asserting that a command object was dispatched. Only the boundaries
(`IConfig`/`IThreadManager`) are mocked, and every fixture comes from this
package's `conftest.py` rather than a local copy of it.
"""

from __future__ import annotations

import os
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingBlockReason,
    EnableTradingResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trading.trading_presenter import (
    TradingPresenter,
)


def _position(symbol="BTCUSDT") -> LivePosition:
    from datetime import UTC, datetime

    return LivePosition(
        symbol=symbol,
        position_amt=Decimal("0.5"),
        entry_price=Decimal("64000.00"),
        mark_price=Decimal("64500.00"),
        unrealized_pnl=Decimal("10.0"),
        leverage=10,
        margin_type=MarginType.CROSSED,
        liquidation_price=None,
        updated_at=datetime.now(UTC),
    )


def _order(symbol="BTCUSDT", status=OrderStatus.NEW, order_time=None) -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.5"),
        status=status,
        price=Decimal("64000.00"),
        order_time=order_time,
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_construction_reflects_the_session_state(
    qapp, view, container, trading_session
):
    presenter = TradingPresenter(view, container)

    assert presenter._view_model.enabled is False
    assert presenter._active_symbol == "BTCUSDT"


def test_construction_when_already_enabled_reflects_that_too(
    qapp, view, container, trading_session
):
    trading_session.set_enabled(enabled=True)

    presenter = TradingPresenter(view, container)

    assert presenter._view_model.enabled is True


# ---------------------------------------------------------------------------
# Toggle -> submits the right background method
# ---------------------------------------------------------------------------


def test_toggle_when_disabled_submits_enable(presenter, mock_thread_manager):
    presenter._view_model.toggleRequested.emit()

    mock_thread_manager.submit.assert_called_once()
    submitted_callable = mock_thread_manager.submit.call_args[0][0]
    assert submitted_callable == presenter._run_enable
    assert presenter._view_model.toggleBusy is True


def test_toggle_when_enabled_submits_disable(
    qapp, view, container, trading_session, mock_thread_manager
):
    trading_session.set_enabled(enabled=True)
    presenter = TradingPresenter(view, container)
    mock_thread_manager.submit.reset_mock()

    presenter._view_model.toggleRequested.emit()

    mock_thread_manager.submit.assert_called_once()
    submitted_callable = mock_thread_manager.submit.call_args[0][0]
    assert submitted_callable == presenter._run_disable


# ---------------------------------------------------------------------------
# Enable outcomes
# ---------------------------------------------------------------------------


def test_successful_enable_turns_the_toggle_on_and_seeds_open_orders(
    presenter, trading_session, view
):
    order = _order()
    trading_session.enable_answers(
        EnableTradingResult(
            enabled=True,
            block_reason=None,
            reconciled_positions=(),
            reconciled_open_orders=(order,),
        )
    )
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)

    assert trading_session.enables == 1
    assert presenter._view_model.enabled is True
    assert presenter._view_model.toggleBusy is False
    assert presenter._view_model.statusIsError is False
    view.set_open_orders.assert_called_once_with([build_open_order_row(order)])
    view.set_positions.assert_called_once_with([])


def test_refused_enable_shows_the_block_reason_and_seeds_positions(
    presenter, trading_session, view
):
    position = _position()
    trading_session.enable_answers(
        EnableTradingResult(
            enabled=False,
            block_reason=EnableTradingBlockReason.UNEXPECTED_POSITIONS,
            reconciled_positions=(position,),
            reconciled_open_orders=(),
        )
    )
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)

    assert presenter._view_model.enabled is False
    assert presenter._view_model.statusIsError is True
    assert "unexpected open positions" in presenter._view_model.statusMessage
    view.set_positions.assert_called_once_with([build_position_row(position)])


def test_an_exception_from_the_session_port_is_reported_not_raised(
    presenter, trading_session
):
    trading_session.enable_raises(RuntimeError("boom"))
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)  # must not raise

    assert presenter._view_model.statusIsError is True
    assert "boom" in presenter._view_model.statusMessage


def test_a_stale_enable_result_from_a_superseded_click_is_discarded(
    presenter, trading_session, view
):
    presenter._view_model.toggleRequested.emit()
    stale_action_id = presenter._toggle_tracker.active_action.action_id

    presenter._view_model.toggleRequested.emit()  # supersedes the first

    trading_session.enable_answers(
        EnableTradingResult(
            enabled=True,
            block_reason=None,
            reconciled_positions=(),
            reconciled_open_orders=(),
        )
    )
    presenter._run_enable(stale_action_id)  # arrives late

    view.set_open_orders.assert_not_called()


# ---------------------------------------------------------------------------
# Disable outcome
# ---------------------------------------------------------------------------


def test_successful_disable_turns_the_toggle_off(
    qapp, view, container, trading_session
):
    trading_session.set_enabled(enabled=True)
    presenter = TradingPresenter(view, container)
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_disable(action_id)

    assert trading_session.disables == 1
    assert presenter._view_model.enabled is False
    assert presenter._view_model.toggleBusy is False
