"""`BOT-169`, `BUG-170` — what the account tabs tell the user when a cancel or a
close fails: a message box per command, the exception's text only behind Details,
and a close of unknown outcome never worded as failed.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderNotPlacedError,
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.position_close_order import (
    ConfirmedClose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    build_position_row,
)

from .account_tabs_desk import AccountTabsDesk
from .account_tabs_fixtures import order, position

_VENUE = "futures_testnet"


def _confirmed() -> ConfirmedClose:
    row = build_position_row(position("BTCUSDT", "0.02"))
    return ConfirmedClose(row.symbol, row.side, row.quantity)


def _open_position(qtbot) -> AccountTabsDesk:
    desk = AccountTabsDesk(qtbot)
    desk.snapshot.holding([position("BTCUSDT", "0.02")])
    desk.presenter.show_symbol("BTCUSDT")
    return desk


def test_a_close_of_unknown_outcome_may_be_live_and_is_never_called_failed(
    qtbot,
) -> None:
    desk = _open_position(qtbot)
    desk.submission.submit_raises(
        OrderOutcomeUnknownError("BTCUSDT", "SEW-close", "502 Bad Gateway <html>")
    )

    desk.panel.closePositionRequested.emit(_confirmed())

    notice = desk.notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert notice.cause == f"trading.{_VENUE}.close.outcome_unknown"
    assert "may be live" in notice.headline
    assert "Open orders and Positions" in notice.headline
    for wrong in ("rejected", "failed", "not placed", "502"):
        assert wrong not in notice.headline
    assert "502 Bad Gateway" in notice.detail
    assert desk.message() == notice.headline


def test_a_close_the_exchange_does_not_hold_is_said_not_placed(qtbot) -> None:
    desk = _open_position(qtbot)
    desk.submission.submit_raises(OrderNotPlacedError("BTCUSDT", "SEW-close", "gone"))

    desk.panel.closePositionRequested.emit(_confirmed())

    notice = desk.notifier.last
    assert notice.cause == f"trading.{_VENUE}.close.not_placed"
    assert "no such" in notice.headline
    assert "may be live" not in notice.headline


def test_a_close_that_raises_hides_no_text_in_the_headline(qtbot) -> None:
    desk = _open_position(qtbot)
    desk.submission.submit_raises(RuntimeError("connection reset"))

    desk.panel.closePositionRequested.emit(_confirmed())

    notice = desk.notifier.last
    assert notice.cause == f"trading.{_VENUE}.close.failed"
    assert notice.detail == "connection reset"
    assert "connection reset" not in notice.headline
    assert "connection reset" not in desk.message()


def test_a_close_with_no_position_is_a_command_refusal(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.closePositionRequested.emit(_confirmed())

    assert desk.notifier.last.kind is FailureKind.COMMAND
    assert desk.notifier.last.headline == "No open BTCUSDT position to close."


def test_a_cancel_that_raises_names_the_order_and_keeps_the_text_as_detail(
    qtbot, monkeypatch
) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.activity.holding_open_orders([order("BTCUSDT", "SEW-btc")])
    desk.presenter.show_symbol("BTCUSDT")
    monkeypatch.setattr(desk.submission, "cancel", _failing_cancel)

    desk.panel.cancelRequested.emit("BTCUSDT", "SEW-btc")

    notice = desk.notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert notice.cause == f"trading.{_VENUE}.cancel"
    assert "BTCUSDT SEW-btc" in notice.headline
    assert "Unknown order sent" not in notice.headline
    assert "Unknown order sent" in notice.detail
    assert "Unknown order sent" not in desk.message()
    assert desk.open_order_ids() == ["SEW-btc"]


def _failing_cancel(symbol: str, client_order_id: str):
    raise RuntimeError("Unknown order sent")


def test_a_safety_gate_refusal_of_a_cancel_is_a_command_failure(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.activity.holding_open_orders([order("BTCUSDT", "SEW-btc")])
    desk.submission.cancel_answers(
        CancelOrderResult(ExecuteOrderSafetyGate.TRADING_SWITCH_OFF, None)
    )
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.cancelRequested.emit("BTCUSDT", "SEW-btc")

    assert desk.notifier.last.kind is FailureKind.COMMAND
    assert desk.notifier.last.headline == desk.message()


def test_a_successful_cancel_tells_no_failure(qtbot) -> None:
    desk = AccountTabsDesk(qtbot)
    desk.activity.holding_open_orders([order("BTCUSDT", "SEW-btc")])
    desk.submission.cancel_answers(CancelOrderResult(None, order("BTCUSDT", "SEW-btc")))
    desk.presenter.show_symbol("BTCUSDT")

    desk.panel.cancelRequested.emit("BTCUSDT", "SEW-btc")

    assert desk.notifier.failures == []
