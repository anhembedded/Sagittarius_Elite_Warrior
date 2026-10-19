"""`BOT-169`, `BUG-170` — what the order panel tells the user when it fails.

Every failure goes through `INotifier`: the headline is a sentence the panel
wrote, the exception's text is the notice's `detail`, and an order whose
outcome is unknown is never worded as rejected.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta, timezone

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_failure import (
    SubmitFailure,
    SubmitFailureKind,
    submit_failure_headline,
    submit_failure_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.binance_error_codes import (
    EXCHANGE_PAUSE_TAG,
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


def test_an_order_the_exchanges_pause_refused_is_shown_to_the_user_and_logged_at_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`BUG-217`: the log filter writes the Engine's dispatcher ERROR for a call the pause
    refused at DEBUG. That is only safe because the desk tells its user itself: a command
    failure notice, the panel's own error line, and a WARNING from the presenter
    (`order_entry_presenter._on_submitted`). This pins all three for a manual order."""
    panel = _ready_buy()
    pause = ExchangeRateLimitedError(
        timedelta(seconds=30),
        banned=False,
        raw_message=f"no request is sent for another 30 s {EXCHANGE_PAUSE_TAG}",
    )
    panel.submission.submit_raises(pause)
    caplog.set_level(logging.DEBUG)

    panel.vm.intents.request_submit(EntrySide.BUY)

    notice = panel.notifier.last
    assert notice.kind is FailureKind.COMMAND
    assert "asked for a pause" in notice.headline
    assert "order was not sent" in notice.headline
    assert re.search(
        r"until \d{4}-\d\d-\d\d \d\d:\d\d:\d\d[+-]\d\d:\d\d\. Try", notice.headline
    )
    assert panel.vm.message == notice.headline
    assert notice.cause == f"trading.{_VENUE}.order.paused"
    assert EXCHANGE_PAUSE_TAG in notice.detail
    warned = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("order failed" in message for message in warned), warned


def _pause(*, banned: bool) -> ExchangeRateLimitedError:
    return ExchangeRateLimitedError(
        timedelta(seconds=90), banned=banned, raw_message=EXCHANGE_PAUSE_TAG
    )


def test_a_pause_says_when_it_ends_in_the_machines_zone_with_its_offset() -> None:
    """`BOT-181`: the error carries how long the pause lasts; the failure dates its end.
    A fixed non-UTC zone is injected, so a conversion that fell back to UTC goes red
    on a UTC runner too."""
    began = datetime(2026, 10, 19, 12, 0, 0, tzinfo=UTC)
    vietnam = timezone(timedelta(hours=7))

    failure = submit_failure_of(_pause(banned=False), now=lambda: began)

    assert failure.kind is SubmitFailureKind.PAUSED
    assert failure.resume_at == began + timedelta(seconds=90)
    assert submit_failure_headline(failure, "order", zone=vietnam) == (
        "The exchange asked for a pause: the order was not sent, and nothing can be "
        "sent until 2026-10-19 19:01:30+07:00. Try again then."
    )


def test_a_pause_with_no_known_end_does_not_name_a_time() -> None:
    failure = SubmitFailure(SubmitFailureKind.PAUSED, "paused")

    assert submit_failure_headline(failure, "order") == (
        "The exchange asked for a pause: the order was not sent. Try again in a while."
    )


def test_a_ban_says_it_is_a_ban_and_names_the_action_it_refused() -> None:
    failure = submit_failure_of(_pause(banned=True))

    assert failure.kind is SubmitFailureKind.BANNED
    headline = submit_failure_headline(failure, "close order")
    assert headline.startswith("The exchange has banned this machine's requests")
    assert "the close order was not sent" in headline
    assert "asked for a pause" not in headline


def test_a_failure_that_is_not_a_pause_keeps_its_words_and_has_no_end() -> None:
    failure = submit_failure_of(RuntimeError("connection reset"))

    assert failure.kind is SubmitFailureKind.FAILED
    assert failure.resume_at is None
    assert submit_failure_headline(failure, "order") == (
        "The order could not be sent. Check Open orders and Positions, then try again."
    )


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
    assert "no such" in notice.headline
    assert "Check Open orders before sending it again" in notice.headline
    assert "Nothing is live" not in notice.headline
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


def test_an_unknown_outcome_is_told_even_when_the_action_was_superseded() -> None:
    """The panel moved on (another symbol), but the order may be live."""
    panel = _ready_buy()
    stale = SubmitFailure(SubmitFailureKind.OUTCOME_UNKNOWN, "502")

    panel.presenter._on_submitted((999, EntrySide.BUY, None, stale, False))

    assert "may be live" in panel.notifier.last.headline


def test_a_superseded_plain_failure_stays_quiet() -> None:
    panel = _ready_buy()
    stale = SubmitFailure(SubmitFailureKind.FAILED, "boom")

    panel.presenter._on_submitted((999, EntrySide.BUY, None, stale, False))

    assert panel.notifier.failures == []
