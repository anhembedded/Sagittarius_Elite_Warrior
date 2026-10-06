"""`EPIC-028O` — what the order panel asks the submission path for, per
order kind: a stop-limit carries its stop and the last price it is judged
against, a quote-sized market buy carries the quote it spends, and the
panel's maxima use the app's per-order notional limit it read at load."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.stop_price_check import (
    StopPriceCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    DEFAULT_ORDER_NOTIONAL_LIMIT,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)

from .order_entry_fixtures import SYMBOL
from .order_entry_presenter_fixtures import (
    PresentedPanel,
    canned_preview,
    placed,
    presented_panel,
)

_BUY = EntrySide.BUY
_SELL = EntrySide.SELL


def _loaded(last_price: str) -> PresentedPanel:
    panel = presented_panel()
    panel.presenter.show_symbol(SYMBOL)
    panel.presenter.update_last_price(Decimal(last_price))
    return panel


def test_the_load_reads_the_app_notional_limit() -> None:
    panel = presented_panel()

    panel.presenter.show_symbol(SYMBOL)

    assert panel.vm.context is not None
    assert panel.vm.context.notional_limit == DEFAULT_ORDER_NOTIONAL_LIMIT


def test_a_quote_sized_buy_asks_to_spend_its_total() -> None:
    panel = _loaded("250")
    panel.vm.intents.set_order_type(OrderType.MARKET)
    panel.vm.intents.set_total(_BUY, "450")
    estimate = canned_preview(OrderSide.BUY, "1.8", None)
    preview = replace(
        estimate, order=replace(estimate.order, quote_quantity=Decimal(450))
    )
    panel.submission.preview_answers(preview)
    panel.submission.submit_answers(placed(preview.order))

    panel.vm.intents.request_submit(_BUY)

    asked = panel.submission.previewed[0]
    assert asked.order_type is OrderType.MARKET
    assert asked.quote_quantity == 450
    assert asked.quantity == Decimal("1.8")  # the estimate at the last price
    assert asked.reference_price == 250
    assert asked.stop_price is None
    sent = panel.submission.submitted_live[0]
    assert sent.quote_quantity == 450
    assert sent.side is OrderSide.BUY
    assert panel.confirm.asked[0].question.startswith("Spend 450.00 USDT to buy BTC")
    assert panel.vm.entry(_BUY).total is None  # cleared after the fill


def test_a_quote_sized_buy_too_small_for_one_lot_is_still_confirmed() -> None:
    # The exchange sizes it from the quote; only its notional is checked.
    panel = _loaded("250")
    panel.vm.intents.set_order_type(OrderType.MARKET)
    panel.vm.intents.set_total(_BUY, "20")
    estimate = canned_preview(OrderSide.BUY, "0", None)
    panel.submission.preview_answers(
        replace(estimate, order=replace(estimate.order, quote_quantity=Decimal(20)))
    )

    panel.vm.intents.request_submit(_BUY)

    assert len(panel.confirm.asked) == 1


def test_a_stop_limit_carries_its_stop_and_the_last_price() -> None:
    panel = _loaded("100")
    panel.vm.intents.set_order_type(OrderType.STOP_LIMIT)
    panel.vm.intents.set_stop_price(_SELL, "95")
    panel.vm.intents.set_price(_SELL, "94")
    panel.vm.intents.set_quantity(_SELL, "0.2")
    limit = canned_preview(OrderSide.SELL, "0.2", "94")
    preview = replace(
        limit,
        order=replace(
            limit.order, order_type=OrderType.STOP_LIMIT, stop_price=Decimal(95)
        ),
        stop_check=StopPriceCheck.ON_TRIGGER_SIDE,
    )
    panel.submission.preview_answers(preview)
    panel.submission.submit_answers(placed(preview.order))

    panel.vm.intents.request_submit(_SELL)

    asked = panel.submission.previewed[0]
    assert asked.order_type is OrderType.STOP_LIMIT
    assert (asked.stop_price, asked.last_price) == (95, 100)
    assert asked.reference_price == 94
    assert asked.quote_quantity is None
    sent = panel.submission.submitted_live[0]
    assert (sent.stop_price, sent.last_price) == (95, 100)
    assert "once the price reaches 95.0000 USDT" in panel.confirm.asked[0].question


def test_a_limit_order_carries_no_stop_and_no_quote() -> None:
    panel = _loaded("100")
    panel.vm.intents.set_stop_price(_BUY, "105")  # typed on another tab, then left
    panel.vm.intents.set_price(_BUY, "100")
    panel.vm.intents.set_quantity(_BUY, "1")
    panel.submission.preview_answers(canned_preview(OrderSide.BUY, "1", "100"))

    panel.vm.intents.request_submit(_BUY)

    asked = panel.submission.previewed[0]
    assert asked.stop_price is None
    assert asked.last_price is None
    assert asked.quote_quantity is None


def test_a_stop_crossed_by_the_time_of_the_preview_is_not_confirmed() -> None:
    panel = _loaded("100")
    panel.vm.intents.set_order_type(OrderType.STOP_LIMIT)
    panel.vm.intents.set_stop_price(_BUY, "105")
    panel.vm.intents.set_price(_BUY, "106")
    panel.vm.intents.set_quantity(_BUY, "1")
    limit = canned_preview(OrderSide.BUY, "1", "106")
    panel.submission.preview_answers(
        replace(
            limit,
            order=replace(
                limit.order, order_type=OrderType.STOP_LIMIT, stop_price=Decimal(105)
            ),
            stop_check=StopPriceCheck.WRONG_SIDE,
        )
    )

    panel.vm.intents.request_submit(_BUY)

    assert panel.confirm.asked == []
    assert panel.submission.submitted_live == []
    assert panel.vm.message_is_error
    assert "already been crossed" in panel.vm.message


def test_a_preview_worth_more_than_the_limit_is_not_confirmed() -> None:
    # The gate's own figure (rounded quantity x rounded price) decides.
    panel = _loaded("100")
    panel.vm.intents.set_price(_BUY, "100")
    panel.vm.intents.set_quantity(_BUY, "1")
    panel.submission.preview_answers(
        replace(
            canned_preview(OrderSide.BUY, "1", "100"),
            estimated_notional=DEFAULT_ORDER_NOTIONAL_LIMIT + Decimal("0.01"),
        )
    )

    panel.vm.intents.request_submit(_BUY)

    assert panel.confirm.asked == []
    assert panel.vm.message_is_error
    assert "more than the app's limit" in panel.vm.message
