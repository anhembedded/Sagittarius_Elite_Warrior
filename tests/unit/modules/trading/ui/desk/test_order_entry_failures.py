"""`BOT-169`, `BUG-170` — what the order panel tells the user when it fails.

Every failure goes through `INotifier`: the headline is a sentence the panel
wrote, the exception's text is the notice's `detail`, and an order whose
outcome is unknown is never worded as rejected.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderNotPlacedError,
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
)

from .order_entry_fixtures import SYMBOL
from .order_entry_presenter_fixtures import (
    PresentedPanel,
    canned_preview,
    placed,
    presented_panel,
)

_VENUE = "spot_testnet"


def _ready_buy() -> PresentedPanel:
    panel = presented_panel()
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.intents.set_price(EntrySide.BUY, "100")
    panel.vm.intents.set_quantity(EntrySide.BUY, "1")
    panel.submission.preview_answers(canned_preview(OrderSide.BUY, "1", "100"))
    return panel


def test_an_order_whose_outcome_is_unknown_says_it_may_be_live() -> None:
    panel = _ready_buy()
    panel.submission.submit_raises(
        OrderOutcomeUnknownError(SYMBOL, "SEW-1", "502 Bad Gateway <html>")
    )

    panel.vm.intents.request_submit(EntrySide.BUY)

    notice = panel.notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert notice.cause == f"trading.{_VENUE}.order.outcome_unknown"
    assert "may be live" in notice.headline
    assert "Open orders and Positions" in notice.headline
    for wrong in ("rejected", "failed", "not placed", "502"):
        assert wrong not in notice.headline
    assert "502 Bad Gateway" in notice.detail
    assert notice.retry is None
    assert panel.vm.message == notice.headline
    assert panel.vm.message_is_error
    assert panel.vm.entry(EntrySide.BUY).quantity == 1  # kept: nothing is known


def test_an_order_the_exchange_does_not_hold_is_said_not_placed() -> None:
    panel = _ready_buy()
    panel.submission.submit_raises(
        OrderNotPlacedError(SYMBOL, "SEW-1", "unknown order")
    )

    panel.vm.intents.request_submit(EntrySide.BUY)

    notice = panel.notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert notice.cause == f"trading.{_VENUE}.order.not_placed"
    assert "was not placed" in notice.headline
    assert "may be live" not in notice.headline
    assert "unknown order" in notice.detail


def test_any_other_failure_to_send_is_a_command_failure_with_the_text_as_detail() -> (
    None
):
    panel = _ready_buy()
    panel.submission.submit_raises(RuntimeError("connection reset"))

    panel.vm.intents.request_submit(EntrySide.BUY)

    notice = panel.notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert notice.cause == f"trading.{_VENUE}.order.failed"
    assert "connection reset" not in notice.headline
    assert "connection reset" not in panel.vm.message
    assert notice.detail == "connection reset"
    assert "may be live" not in notice.headline


def test_an_order_that_cannot_be_checked_is_a_command_failure() -> None:
    panel = presented_panel()  # no preview seeded: the check raises
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.intents.set_price(EntrySide.BUY, "100")
    panel.vm.intents.set_quantity(EntrySide.BUY, "1")

    panel.vm.intents.request_submit(EntrySide.BUY)

    notice = panel.notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert notice.cause == f"trading.{_VENUE}.order.preview"
    assert notice.detail != ""
    assert notice.detail not in notice.headline
    assert panel.vm.message == "The order could not be checked. Try again."
    assert panel.submission.submitted_live == []


def test_an_order_the_safety_gate_blocks_is_told_in_its_authored_words() -> None:
    panel = _ready_buy()
    panel.submission.submit_answers(
        ExecuteOrderResult(
            blocked_by=ExecuteOrderSafetyGate.TRADING_SWITCH_OFF,
            preview=None,
            limit_checks=(),
            submitted_order=None,
        )
    )

    panel.vm.intents.request_submit(EntrySide.BUY)

    notice = panel.notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert notice.headline == format_execute_order_block_reason(
        ExecuteOrderSafetyGate.TRADING_SWITCH_OFF
    )


def test_an_unreadable_symbol_is_a_background_notice_with_retry() -> None:
    panel = presented_panel()

    panel.presenter.show_symbol("NOPEUSDT")

    notice = panel.notifier.last
    assert notice.kind is FailureKind.BACKGROUND
    assert notice.cause == f"trading.{_VENUE}.order_terms"
    assert notice.scope == TRADE_ROUTE
    assert notice.retry == panel.presenter.refresh
    assert notice.detail != ""
    assert notice.detail not in notice.headline
    assert panel.vm.message == "NOPEUSDT could not be read."


def test_reading_the_symbol_again_clears_the_notice() -> None:
    panel = presented_panel()
    panel.presenter.show_symbol(SYMBOL)

    assert panel.notifier.cleared == [f"trading.{_VENUE}.order_terms"]
    assert panel.notifier.failures == []


def test_a_placed_order_tells_no_failure() -> None:
    panel = _ready_buy()
    panel.submission.submit_answers(
        placed(canned_preview(OrderSide.BUY, "1", "100").order)
    )

    panel.vm.intents.request_submit(EntrySide.BUY)

    assert panel.notifier.failures == []
