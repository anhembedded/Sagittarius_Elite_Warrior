"""`EPIC-024B` §5 — the real-Qt-click integration test the original plan
mandated for the Dev Board manual order card, mirroring
`test_dev_board_known_gaps.py::test_strategy_dropdown_arms_the_selected_strategy`'s
pattern: a real `navigate()`-booted app, `qtbot.mouseClick()` on the actual
LONG/SHORT `QPushButton`s, and (per `conftest.py`'s `mock_dispatch`) the
REAL `ExecuteOrderCommandHandler` for the not-armed path — not a fabricated
result standing in for it.

Two things, not the whole safety-gate/limits matrix (already covered by
`tests/unit/application/use_cases/trading/test_execute_order.py` and
`tests/unit/presentation/ui/screens/test_dashboard_presenter.py` at the
unit level — this file's job is only to prove the click is really wired to
that pipeline, not to re-derive its business rules):

1. A real click on the symbol a strategy is armed on reaches the real
   pipeline and shows the pipeline's own refusal. Until `EPIC-025` PR 2.1f
   the screen refused it itself, before any dispatch; that rule is now
   `ExecuteOrderSafetyGate.SYMBOL_LEASED` on the order path, and this test's
   own docstring says why this suite cannot show that particular gate.
2. A real click on an unarmed symbol genuinely reaches the real
   `ExecuteOrderCommandHandler` and shows its real safety-gate refusal —
   this suite's app always boots with `TradingVenue.DISABLED`
   (`src/config/app_config.json`), so the click is provably real (a fake
   dispatcher branch could not produce this exact, handler-owned message)
   while touching no network.
"""

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType

_TRADING_VENUE_DISABLED_MESSAGE = (
    "Manual order blocked: Trading venue is disabled in configuration — only "
    "Futures Testnet is supported."
)


def _open_dashboard(navigate):
    cfg = navigate("dashboard")
    return cfg["presenter_instance"], cfg["view_instance"]


def _set_limit_order(panel, price: float, quantity: float) -> None:
    """Switches the manual order card to Limit and fills in a valid price/
    quantity — Market mode needs a live tick's `_last_price_by_symbol`
    entry this offscreen suite never produces, so Limit is the only mode a
    real click can pass `_on_manual_order_requested`'s own validation with."""
    index = panel._cbo_manual_order_type.findData(OrderType.LIMIT.name)
    assert index >= 0
    panel._cbo_manual_order_type.setCurrentIndex(index)
    panel._spn_manual_price.setValue(price)
    panel._spn_manual_quantity.setValue(quantity)


def _spy_on_dispatch(monkeypatch, presenter) -> list:
    """Records every `handler_class` this presenter's dispatcher is asked
    to resolve, while still delegating to the real (fixture-mocked)
    dispatch — so a test can assert "no dispatch happened at all" instead
    of only inspecting the end state."""
    calls: list = []
    original = presenter.dispatcher.dispatch

    def _spy(handler_class, input_dto=None):
        calls.append(handler_class)
        return original(handler_class, input_dto)

    monkeypatch.setattr(presenter.dispatcher, "dispatch", _spy)
    return calls


def test_a_real_long_click_on_the_armed_symbol_reaches_the_real_pipeline(
    qtbot, main_window, navigate, monkeypatch
):
    """Arms `ema_crossover` on the card's own active symbol, then clicks the
    real "LONG" button.

    @par What changed, and what this test can and cannot prove
    Before `EPIC-025` PR 2.1f this asserted the opposite of what it asserts
    now: that the click was blocked *before any dispatch at all*, because
    `DashboardPresenter._run_manual_order()` read `IArmedStrategy.armed()` and
    refused on the spot. That rule now lives on the order path as
    `ExecuteOrderSafetyGate.SYMBOL_LEASED`, so every caller inherits it rather
    than one form — and the click therefore *does* go through the pipeline,
    which is what this asserts instead.

    It cannot show the lease refusal itself, and the reason is this suite's own
    fixture: the app boots with `TradingVenue.DISABLED`
    (`src/config/app_config.json`), so `TRADING_VENUE_DISABLED` fires first —
    correctly, since "this app cannot trade at all" is a more fundamental
    refusal than "not this symbol". The lease's own proof is at the unit level,
    where the venue is enabled:
    `tests/unit/modules/trading/application/orders/test_execute_order.py`
    (refused for another owner, allowed for the holder, and refused before any
    network call) and `tests/unit/modules/strategy/application/use_cases/
    test_arm_strategy.py` (arming claims it, disarming gives it back).

    What is left here is still worth a real click: that arming no longer
    short-circuits the screen's own order path, and that the operator sees the
    real handler's refusal rather than a message the screen invented.
    """
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    panel = view._panel

    index = panel._cbo_live_strategy.findData("ema_crossover")
    assert index >= 0, "ema_crossover must be a real registered strategy"
    panel._cbo_live_strategy.setCurrentIndex(index)
    panel._cbo_live_interval.setCurrentText("5m")
    qtbot.mouseClick(panel._btn_arm_strategy, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: presenter._view_model.strategy.armedSummary != "", timeout=2000
    )
    assert presenter._armed_strategy.armed().config.symbol == presenter._active_symbol

    # Spy installed only now — arming itself legitimately dispatches
    # `ArmStrategyCommandHandler`; what this test reads is the dispatches the
    # *manual order click that follows* makes.
    calls = _spy_on_dispatch(monkeypatch, presenter)
    _set_limit_order(panel, price=50000.0, quantity=0.01)
    qtbot.mouseClick(panel._btn_manual_long, Qt.MouseButton.LeftButton)
    # The exact final text, not merely "non-empty": the click synchronously
    # sets a transient "Đang gửi lệnh..." status before the background worker
    # reports the real outcome, so a bare `!= ""` check would race.
    qtbot.waitUntil(
        lambda: (
            panel._lbl_manual_order_status.text() == _TRADING_VENUE_DISABLED_MESSAGE
        ),
        timeout=2000,
    )

    assert ExecuteOrderCommand in calls, (
        "the click must now reach the real order pipeline — the screen no "
        f"longer refuses on its own; got {calls!r}"
    )


def test_a_real_short_click_on_an_unarmed_symbol_reaches_the_real_execute_order_handler(
    qtbot, main_window, navigate, monkeypatch
):
    """No strategy armed here (the default state `navigate()` leaves the
    Dev Board in) — the click must fall through to a real
    `GetOpenPositionsQuery` dispatch and then a real `ExecuteOrderCommand`
    dispatch, landing on the REAL `ExecuteOrderCommandHandler`'s own
    `TRADING_VENUE_DISABLED` safety gate (this suite's app always boots
    with `TradingVenue.DISABLED` — see `conftest.py`'s `mock_dispatch`).
    A fabricated dispatcher response could report almost any text; this
    exact, handler-owned message is only reachable by actually running
    that handler."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    panel = view._panel
    calls = _spy_on_dispatch(monkeypatch, presenter)
    assert not presenter._armed_strategy.armed().engine_running

    _set_limit_order(panel, price=50000.0, quantity=0.01)
    qtbot.mouseClick(panel._btn_manual_short, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: (
            panel._lbl_manual_order_status.text() == _TRADING_VENUE_DISABLED_MESSAGE
        ),
        timeout=2000,
    )

    assert calls == [GetOpenPositionsQuery, ExecuteOrderCommand]
