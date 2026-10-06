"""`EPIC-028H` — the order panel reads its venue's terms and account, and
places an order preview → confirm → submit, through the one submission path.

@details Every port is a verified fake (`fake_venue_ports`), every background
task runs inline or is held by the test, and the confirmation dialog is a
recorded answer, so each step's effect is visible without a running exchange
or a modal dialog."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    NotionalCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_presenter import (
    OrderEntryPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .order_entry_fixtures import (
    SYMBOL,
    TERMS,
    HeldThreadManager,
    InlineThreadManager,
    spot_status,
)
from .order_entry_presenter_fixtures import (
    SPOT,
    Answers,
    canned_preview,
    placed,
    presented_panel,
)


def test_showing_a_symbol_reads_its_terms_and_the_account() -> None:
    panel = presented_panel()

    panel.presenter.show_symbol(SYMBOL)

    context = panel.vm.context
    assert context is not None
    assert context.terms == TERMS
    assert (context.base_asset, context.quote_asset) == ("BTC", "USDT")
    assert context.available_quote == 1000
    assert context.free_base == Decimal("0.5")
    assert panel.terms.reads == [SYMBOL]


def test_an_account_without_the_base_asset_has_none_to_sell() -> None:
    panel = presented_panel(account=FakeAccountSnapshot(spot_status(btc_free=None)))

    panel.presenter.show_symbol(SYMBOL)

    assert panel.vm.context is not None
    assert panel.vm.context.free_base == 0


def test_an_unreachable_account_leaves_the_balances_unknown() -> None:
    panel = presented_panel(account=FakeAccountSnapshot())  # unconfigured: unreachable

    panel.presenter.show_symbol(SYMBOL)

    assert panel.vm.context is not None
    assert panel.vm.context.available_quote is None
    assert panel.vm.context.free_base is None


def test_a_summary_on_an_unreachable_status_is_not_trusted() -> None:
    stale = replace(spot_status(), reachable=False)
    panel = presented_panel(account=FakeAccountSnapshot(stale))

    panel.presenter.show_symbol(SYMBOL)

    assert panel.vm.context is not None
    assert panel.vm.context.available_quote is None
    assert panel.vm.context.free_base is None


def test_a_symbol_the_venue_does_not_list_is_reported() -> None:
    panel = presented_panel()

    panel.presenter.show_symbol("NOPEUSDT")

    assert panel.vm.context is None
    assert panel.vm.message_is_error
    assert "NOPEUSDT" in panel.vm.message


def test_a_superseded_load_is_dropped() -> None:
    threads = HeldThreadManager()
    panel = presented_panel(threads=threads)
    panel.presenter.show_symbol("NOPEUSDT")
    panel.presenter.show_symbol(SYMBOL)

    threads.run(1)
    threads.run(0)  # the old symbol's failure answers last

    assert panel.vm.context is not None
    assert not panel.vm.message_is_error


def test_the_panel_refuses_another_venues_ports() -> None:
    vm = OrderEntryViewModel(desk_profile_for(SPOT))

    with pytest.raises(ValueError, match="futures_testnet"):
        OrderEntryPresenter(
            vm,
            fake_venue_ports(TradingVenue.FUTURES_TESTNET),
            InlineThreadManager(),
            Answers(),
        )


def test_a_confirmed_buy_is_sent_rounded_as_previewed() -> None:
    panel = presented_panel()
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.intents.set_price(EntrySide.BUY, "100")
    panel.vm.intents.set_quantity(EntrySide.BUY, "2.0009")
    preview = canned_preview(OrderSide.BUY, "2.000", "100")
    panel.submission.preview_answers(preview)
    panel.submission.submit_answers(placed(preview.order))

    panel.vm.intents.request_submit(EntrySide.BUY)

    previewed = panel.submission.previewed[0]
    assert previewed.side is OrderSide.BUY
    assert previewed.quantity == Decimal("2.0009")
    sent = panel.submission.submitted_live[0]
    assert sent.symbol == SYMBOL
    assert sent.side is OrderSide.BUY
    assert sent.order_type is OrderType.LIMIT
    assert sent.quantity == Decimal("2.000")
    assert sent.reference_price == 100
    assert sent.reduce_only is False
    assert panel.submission.submitted_dry == []
    assert "Buy 2.000 BTC at 100.0000 USDT" in panel.confirm.asked[0].question
    assert not panel.vm.message_is_error
    assert panel.vm.entry(EntrySide.BUY).quantity is None
    assert panel.terms.reads == [SYMBOL, SYMBOL]  # balances re-read after


def test_a_market_sell_is_priced_at_the_last_price() -> None:
    panel = presented_panel()
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.intents.set_order_type(OrderType.MARKET)
    panel.presenter.update_last_price(Decimal(250))
    panel.vm.intents.set_quantity(EntrySide.SELL, "0.2")
    preview = canned_preview(OrderSide.SELL, "0.2", None)
    panel.submission.preview_answers(preview)
    panel.submission.submit_answers(placed(preview.order))

    panel.vm.intents.request_submit(EntrySide.SELL)

    assert panel.submission.submitted_live[0].reference_price == 250
    assert panel.submission.submitted_live[0].order_type is OrderType.MARKET
    assert panel.submission.submitted_live[0].quote_quantity is None
    assert "about 250.0000 USDT" in panel.confirm.asked[0].question


def test_a_sell_is_sent_as_a_sell_of_the_held_asset() -> None:
    panel = presented_panel()
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.intents.set_price(EntrySide.SELL, "100")
    panel.vm.intents.set_quantity(EntrySide.SELL, "0.2")
    preview = canned_preview(OrderSide.SELL, "0.2", "100")
    panel.submission.preview_answers(preview)
    panel.submission.submit_answers(placed(preview.order))

    panel.vm.intents.request_submit(EntrySide.SELL)

    sent = panel.submission.submitted_live[0]
    assert sent.side is OrderSide.SELL
    assert sent.reduce_only is False


def test_a_sell_whose_holding_is_gone_at_submit_time_is_refused() -> None:
    # The panel loaded a holding, then it was sold elsewhere: the fresh read
    # at submit time, not the panel's copy, decides (`manual_order_intent_for`).
    panel = presented_panel()
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.intents.set_price(EntrySide.SELL, "100")
    panel.vm.intents.set_quantity(EntrySide.SELL, "0.2")
    panel.submission.preview_answers(canned_preview(OrderSide.SELL, "0.2", "100"))
    panel.account.answer_with(spot_status(btc_free=None))

    panel.vm.intents.request_submit(EntrySide.SELL)

    assert panel.submission.submitted_live == []
    assert panel.vm.message_is_error
    assert "no sellable holding" in panel.vm.message


def test_cancelling_the_dialog_sends_nothing() -> None:
    panel = presented_panel(answer=False)
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.intents.set_price(EntrySide.BUY, "100")
    panel.vm.intents.set_quantity(EntrySide.BUY, "1")
    panel.submission.preview_answers(canned_preview(OrderSide.BUY, "1", "100"))

    panel.vm.intents.request_submit(EntrySide.BUY)

    assert panel.submission.submitted_live == []
    assert panel.vm.message == "Order not sent."
    assert not panel.vm.busy


def test_a_side_with_a_problem_is_not_even_previewed() -> None:
    panel = presented_panel()
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.intents.set_price(EntrySide.BUY, "100")  # no amount

    panel.vm.intents.request_submit(EntrySide.BUY)

    assert panel.submission.previewed == []
    assert panel.vm.message == "Enter an amount."
    assert panel.vm.message_is_error


def test_a_preview_below_the_minimum_is_not_confirmed() -> None:
    panel = presented_panel()
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.intents.set_price(EntrySide.BUY, "100")
    panel.vm.intents.set_quantity(EntrySide.BUY, "1")
    preview = canned_preview(OrderSide.BUY, "1", "100")
    panel.submission.preview_answers(
        OrderPreview(
            order=preview.order,
            raw_quantity=preview.raw_quantity,
            estimated_notional=preview.estimated_notional,
            min_notional=Decimal(500),
            step_size=preview.step_size,
            notional_check=NotionalCheck.INSUFFICIENT,
        )
    )

    panel.vm.intents.request_submit(EntrySide.BUY)

    assert panel.confirm.asked == []
    assert "minimum of 500" in panel.vm.message


def test_a_blocked_order_says_which_gate_refused() -> None:
    panel = presented_panel()
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.intents.set_price(EntrySide.BUY, "100")
    panel.vm.intents.set_quantity(EntrySide.BUY, "1")
    panel.submission.preview_answers(canned_preview(OrderSide.BUY, "1", "100"))
    panel.submission.submit_answers(
        ExecuteOrderResult(
            blocked_by=ExecuteOrderSafetyGate.TRADING_SWITCH_OFF,
            preview=None,
            limit_checks=(),
            submitted_order=None,
        )
    )

    panel.vm.intents.request_submit(EntrySide.BUY)

    assert panel.vm.message_is_error
    assert "Trading is OFF" in panel.vm.message
    assert panel.vm.entry(EntrySide.BUY).quantity == 1  # kept, to retry


def test_a_leased_symbol_is_refused_in_the_operators_own_words() -> None:
    """`PRO-003` §4.1.2, on the order path since `EPIC-025` PR 2.1f: a symbol
    an armed strategy holds refuses a hand-placed order, and the refusal
    names why. Re-homed from the Dev Board's F9 dialog (`EPIC-033P`), which
    hosted this same panel."""
    panel = presented_panel()
    panel.presenter.show_symbol(SYMBOL)
    panel.vm.intents.set_price(EntrySide.BUY, "100")
    panel.vm.intents.set_quantity(EntrySide.BUY, "1")
    panel.submission.preview_answers(canned_preview(OrderSide.BUY, "1", "100"))
    panel.submission.submit_answers(
        ExecuteOrderResult(
            blocked_by=ExecuteOrderSafetyGate.SYMBOL_LEASED,
            preview=None,
            limit_checks=(),
            submitted_order=None,
        )
    )

    panel.vm.intents.request_submit(EntrySide.BUY)

    assert panel.vm.message_is_error
    assert (
        format_execute_order_block_reason(ExecuteOrderSafetyGate.SYMBOL_LEASED)
        in panel.vm.message
    )


def test_a_second_submit_while_one_is_out_is_refused() -> None:
    threads = HeldThreadManager()
    panel = presented_panel(threads=threads)
    panel.presenter.show_symbol(SYMBOL)
    threads.run(0)
    panel.vm.intents.set_price(EntrySide.BUY, "100")
    panel.vm.intents.set_quantity(EntrySide.BUY, "1")

    panel.vm.intents.request_submit(EntrySide.BUY)
    panel.vm.intents.request_submit(EntrySide.BUY)

    assert len(threads.pending) == 2  # the load, and one preview
    assert panel.vm.message == "An order is already being placed."
