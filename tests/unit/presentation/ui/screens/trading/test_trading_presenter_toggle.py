"""`EPIC-021I` — the Trading screen's Enable/Disable toggle and its two
live tables (Positions/Open Orders).

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
`test_trading_view_contract.py`. `TradingSessionState` is the real class
(plain state, no I/O) — only the boundaries (`IConfig`/`IDispatcher`/
`IThreadManager`) are mocked.
"""

from __future__ import annotations

import os
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
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.disable_trading import (
    DisableTradingCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.enable_trading import (
    EnableTradingBlockReason,
    EnableTradingCommand,
    EnableTradingResult,
)
from Sagittarius_Elite_Warrior.src.domain.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.position_changed_event import (
    PositionChangedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_presenter import (
    TradingPresenter,
)
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


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
    """Construction itself submits `ChartCoordinator.start()`'s background
    work (loading history for the default symbol) — reset the mock
    afterward so each test's own `assert_called_once()` on the toggle
    reflects only what that test triggered, same reasoning
    `test_dashboard_presenter.py`'s own `presenter` fixture documents."""
    p = TradingPresenter(view, container)
    mock_thread_manager.submit.reset_mock()
    return p


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_construction_reflects_the_session_state(qapp, view, container, session_state):
    presenter = TradingPresenter(view, container)

    assert presenter._view_model.enabled is False
    assert presenter._active_symbol == "BTCUSDT"


def test_construction_when_already_enabled_reflects_that_too(
    qapp, view, container, session_state
):
    session_state.enable({"BTCUSDT"})

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
    qapp, view, container, session_state, mock_thread_manager
):
    session_state.enable(set())
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
    presenter, mock_dispatcher, view
):
    order = _order()
    mock_dispatcher.dispatch.return_value = EnableTradingResult(
        enabled=True,
        block_reason=None,
        reconciled_positions=(),
        reconciled_open_orders=(order,),
    )
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)

    mock_dispatcher.dispatch.assert_called_once_with(
        EnableTradingCommand, EnableTradingCommand()
    )
    assert presenter._view_model.enabled is True
    assert presenter._view_model.toggleBusy is False
    assert presenter._view_model.statusIsError is False
    view.set_open_orders.assert_called_once_with([build_open_order_row(order)])
    view.set_positions.assert_called_once_with([])


def test_refused_enable_shows_the_block_reason_and_seeds_positions(
    presenter, mock_dispatcher, view
):
    position = _position()
    mock_dispatcher.dispatch.return_value = EnableTradingResult(
        enabled=False,
        block_reason=EnableTradingBlockReason.UNEXPECTED_POSITIONS,
        reconciled_positions=(position,),
        reconciled_open_orders=(),
    )
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)

    assert presenter._view_model.enabled is False
    assert presenter._view_model.statusIsError is True
    assert "vị thế mở ngoài dự kiến" in presenter._view_model.statusMessage
    view.set_positions.assert_called_once_with([build_position_row(position)])


def test_an_exception_from_the_dispatcher_is_reported_not_raised(
    presenter, mock_dispatcher
):
    mock_dispatcher.dispatch.side_effect = RuntimeError("boom")
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_enable(action_id)  # must not raise

    assert presenter._view_model.statusIsError is True
    assert "boom" in presenter._view_model.statusMessage


def test_a_stale_enable_result_from_a_superseded_click_is_discarded(
    presenter, mock_dispatcher, view
):
    presenter._view_model.toggleRequested.emit()
    stale_action_id = presenter._toggle_tracker.active_action.action_id

    presenter._view_model.toggleRequested.emit()  # supersedes the first

    mock_dispatcher.dispatch.return_value = EnableTradingResult(
        enabled=True,
        block_reason=None,
        reconciled_positions=(),
        reconciled_open_orders=(),
    )
    presenter._run_enable(stale_action_id)  # arrives late

    view.set_open_orders.assert_not_called()


# ---------------------------------------------------------------------------
# Disable outcome
# ---------------------------------------------------------------------------


def test_successful_disable_turns_the_toggle_off(
    qapp, view, container, session_state, mock_dispatcher
):
    session_state.enable(set())
    presenter = TradingPresenter(view, container)
    presenter._view_model.toggleRequested.emit()
    action_id = presenter._toggle_tracker.active_action.action_id

    presenter._run_disable(action_id)

    mock_dispatcher.dispatch.assert_called_once_with(
        DisableTradingCommand, DisableTradingCommand()
    )
    assert presenter._view_model.enabled is False
    assert presenter._view_model.toggleBusy is False


# ---------------------------------------------------------------------------
# OrderFeed -> the two live tables
# ---------------------------------------------------------------------------


def test_order_filled_with_a_live_status_adds_to_open_orders(presenter, view):
    order = _order(status=OrderStatus.NEW)

    presenter._on_order_filled(
        OrderFilledEvent(order=order, fill_price=Decimal(0), fill_quantity=Decimal(0))
    )

    view.set_open_orders.assert_called_once_with([build_open_order_row(order)])


def test_order_filled_with_a_terminal_status_removes_it(presenter, view):
    live_order = _order(status=OrderStatus.NEW)
    presenter._on_order_filled(
        OrderFilledEvent(
            order=live_order, fill_price=Decimal(0), fill_quantity=Decimal(0)
        )
    )
    view.set_open_orders.reset_mock()

    filled_order = _order(status=OrderStatus.FILLED)
    presenter._on_order_filled(
        OrderFilledEvent(
            order=filled_order, fill_price=Decimal(64000), fill_quantity=Decimal("0.5")
        )
    )

    view.set_open_orders.assert_called_once_with([])


def test_position_changed_updates_the_positions_table(presenter, view):
    position = _position()

    presenter._on_position_changed(PositionChangedEvent(position=position))

    view.set_positions.assert_called_once_with([build_position_row(position)])


# ---------------------------------------------------------------------------
# OrderFeed -> live-fill chart markers (`EPIC-021K` §2.3/§4 — "Integration:
# OrderFilledEvent -> marker đúng vị trí thời gian/giá trên chart")
# ---------------------------------------------------------------------------


def test_order_filled_renders_a_fill_marker_on_the_active_symbols_chart(
    presenter, view
):
    from datetime import UTC, datetime

    from Sagittarius_Elite_Warrior.src.presentation.ui.common.order_fill_marker import (
        order_filled_marker,
    )

    event = OrderFilledEvent(
        order=_order(
            symbol="BTCUSDT", order_time=datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
        ),
        fill_price=Decimal("64000.00"),
        fill_quantity=Decimal("0.5"),
    )
    assert presenter._active_symbol == "BTCUSDT"

    presenter._on_order_filled(event)

    view.chart.set_script_markers.assert_called_once_with(
        "live_fills", [order_filled_marker(event)]
    )


def test_order_filled_for_a_different_symbol_does_not_touch_the_chart(presenter, view):
    event = OrderFilledEvent(
        order=_order(symbol="ETHUSDT"),
        fill_price=Decimal("3000.00"),
        fill_quantity=Decimal(1),
    )
    assert presenter._active_symbol != "ETHUSDT"

    presenter._on_order_filled(event)

    view.chart.set_script_markers.assert_not_called()
    assert presenter._fill_markers_by_symbol["ETHUSDT"] != []
