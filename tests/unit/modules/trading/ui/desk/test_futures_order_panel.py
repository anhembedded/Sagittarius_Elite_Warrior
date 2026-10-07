"""`EPIC-028I` — the Futures order panel: it reads the Futures context on
load and shows the exchange's leverage and margin mode; its time in force
and reduce-only reach the order; its chips send `EPIC-028F`'s commands; an
entry with TP/SL is announced for protection, unless it only reduces.

@details Verified fakes for every port, a recorded "Yes" for the dialog,
and a worker pool that runs inline."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.protective_levels import (
    ProtectiveLevels,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_futures_settings_control import (
    FakeFuturesSettingsControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .account_tabs_fixtures import position
from .futures_entry_fixtures import MARK, futures_status, futures_terms
from .order_entry_fixtures import SYMBOL, HeldThreadManager, InlineThreadManager
from .order_entry_presenter_fixtures import Answers, canned_preview, placed

_FUTURES = TradingVenue.FUTURES_TESTNET


@dataclass
class _Panel:
    vm: OrderEntryViewModel
    presenter: OrderEntryPresenter
    submission: FakeOrderSubmission
    control: FakeFuturesSettingsControl
    terms: FakeOrderEntryTerms
    account: FakeAccountSnapshot
    announced: list[object]
    notifier: RecordingNotifier


def _panel(
    position_amount: str | None = None, threads: IThreadManager | None = None
) -> _Panel:
    submission = FakeOrderSubmission()
    control = FakeFuturesSettingsControl()
    terms = futures_terms()
    positions = [position(SYMBOL, position_amount)] if position_amount else []
    account = FakeAccountSnapshot(futures_status(), positions)
    ports = fake_venue_ports(
        _FUTURES,
        order_submission=submission,
        account_snapshot=account,
        order_entry_terms=terms,
        futures_settings=control,
    )
    vm = OrderEntryViewModel(desk_profile_for(_FUTURES))
    notifier = RecordingNotifier()
    presenter = OrderEntryPresenter(
        vm, ports, threads or InlineThreadManager(), Answers(True), notifier
    )
    announced: list[object] = []
    presenter.entryPlaced.connect(announced.append)
    presenter.show_symbol(SYMBOL)
    vm.presenter_side().set_last_price(MARK)
    return _Panel(
        vm, presenter, submission, control, terms, account, announced, notifier
    )


def _type_limit(vm: OrderEntryViewModel, side: EntrySide, quantity: str) -> None:
    vm.intents.set_order_type(OrderType.LIMIT)
    vm.intents.set_price(side, "60000")
    vm.intents.set_quantity(side, quantity)


def _answers_with_an_order(panel: _Panel, side: OrderSide, quantity: str) -> None:
    preview = canned_preview(side, quantity, "60000")
    panel.submission.preview_answers(preview)
    panel.submission.submit_answers(placed(preview.order))


def test_the_load_reads_the_futures_context_and_shows_the_exchanges_setting() -> None:
    panel = _panel()

    context = panel.vm.context
    assert context is not None and context.futures is not None
    assert context.futures.setting.leverage == 10
    assert panel.vm.options.setting == context.futures.setting
    panel.vm.intents.set_price(EntrySide.BUY, "60000")
    figures = panel.vm.figures(EntrySide.BUY)
    assert figures is not None and figures.max_quantity is not None


def test_time_in_force_and_reduce_only_reach_the_order() -> None:
    panel = _panel(position_amount="0.02")
    panel.vm.options.set_time_in_force(TimeInForce.IOC)
    panel.vm.options.set_reduce_only(True)
    _type_limit(panel.vm, EntrySide.SELL, "0.005")
    _answers_with_an_order(panel, OrderSide.SELL, "0.005")

    panel.vm.intents.request_submit(EntrySide.SELL)

    (sent,) = panel.submission.submitted_live
    assert sent.side is OrderSide.SELL
    assert sent.reduce_only is True
    assert sent.time_in_force is TimeInForce.IOC


def test_a_market_order_carries_no_time_in_force() -> None:
    panel = _panel()
    panel.vm.options.set_time_in_force(TimeInForce.FOK)
    panel.vm.intents.set_order_type(OrderType.MARKET)
    panel.vm.intents.set_quantity(EntrySide.BUY, "0.01")
    _answers_with_an_order(panel, OrderSide.BUY, "0.01")

    panel.vm.intents.request_submit(EntrySide.BUY)

    (sent,) = panel.submission.submitted_live
    assert sent.time_in_force is None


def test_an_entry_with_tp_sl_is_announced_for_protection() -> None:
    panel = _panel()
    panel.vm.options.set_tp_sl_enabled(True)
    panel.vm.options.set_take_profit(EntrySide.BUY, "63000")
    panel.vm.options.set_stop_loss(EntrySide.BUY, "58000")
    _type_limit(panel.vm, EntrySide.BUY, "0.005")
    _answers_with_an_order(panel, OrderSide.BUY, "0.005")

    panel.vm.intents.request_submit(EntrySide.BUY)

    ((order, levels),) = panel.announced
    assert order.side is OrderSide.BUY
    assert levels == ProtectiveLevels(Decimal(63000), Decimal(58000))
    assert "TP/SL follow" in panel.vm.message


def test_levels_typed_with_tp_sl_off_protect_nothing() -> None:
    panel = _panel()
    panel.vm.options.set_take_profit(EntrySide.BUY, "63000")
    _type_limit(panel.vm, EntrySide.BUY, "0.005")
    _answers_with_an_order(panel, OrderSide.BUY, "0.005")

    panel.vm.intents.request_submit(EntrySide.BUY)

    assert panel.announced == []


def test_the_leverage_chip_sends_the_change_and_reads_the_symbol_again() -> None:
    panel = _panel()
    reads = len(panel.terms.reads)

    panel.vm.options.request_leverage(20)

    assert panel.control.leverage_changes == [(SYMBOL, 20)]
    assert panel.vm.message == "Set leverage 20x on BTCUSDT."
    assert not panel.vm.message_is_error
    assert len(panel.terms.reads) == reads + 1


def test_a_refused_margin_change_says_why() -> None:
    panel = _panel()
    panel.control.refuses_with(
        AccountControlRefusal.POSITION_OPEN, "BTCUSDT has an open position"
    )

    panel.vm.options.request_margin_type(MarginType.ISOLATED)

    assert panel.control.margin_changes == [(SYMBOL, MarginType.ISOLATED)]
    assert panel.vm.message_is_error
    assert "BTCUSDT has an open position" in panel.vm.message


def test_the_box_keeps_an_order_reduce_only_when_the_position_went_away() -> None:
    """The figures allowed a reduce-only sell against a long; by the time it
    is sent the account is flat, so the position no longer makes it reducing.
    The ticked box still does, and the exchange refuses it instead of
    opening a short."""
    panel = _panel(position_amount="0.02")
    panel.vm.options.set_reduce_only(True)
    _type_limit(panel.vm, EntrySide.SELL, "0.005")
    _answers_with_an_order(panel, OrderSide.SELL, "0.005")
    panel.account.holding([])

    panel.vm.intents.request_submit(EntrySide.SELL)

    (sent,) = panel.submission.submitted_live
    assert sent.reduce_only is True


def test_an_order_that_closes_a_position_is_not_protected() -> None:
    """A Sell/Short against a long reduces it (`manual_order_intent_for`):
    there is no new position for TP/SL to protect."""
    panel = _panel(position_amount="0.02")
    panel.vm.options.set_tp_sl_enabled(True)
    panel.vm.options.set_take_profit(EntrySide.SELL, "57000")
    panel.vm.options.set_stop_loss(EntrySide.SELL, "62000")
    _type_limit(panel.vm, EntrySide.SELL, "0.005")
    _answers_with_an_order(panel, OrderSide.SELL, "0.005")

    panel.vm.intents.request_submit(EntrySide.SELL)

    (sent,) = panel.submission.submitted_live
    assert sent.reduce_only is True
    assert panel.announced == []


def test_the_box_is_read_when_the_user_asks_not_when_the_order_leaves() -> None:
    """The PR #307 review: the box stays enabled while the order is out, so
    the worker must send the value the user confirmed, not the box's value
    by the time it runs."""
    threads = HeldThreadManager()
    panel = _panel(position_amount="0.02", threads=threads)
    for index in range(len(threads.pending)):
        threads.run(index)
    loaded = len(threads.pending)
    panel.vm.options.set_reduce_only(True)
    _type_limit(panel.vm, EntrySide.SELL, "0.005")
    _answers_with_an_order(panel, OrderSide.SELL, "0.005")
    panel.account.holding([])

    panel.vm.intents.request_submit(EntrySide.SELL)
    threads.run(loaded)  # the preview, then the confirmation
    panel.vm.options.set_reduce_only(False)
    threads.run(loaded + 1)  # the submit

    (sent,) = panel.submission.submitted_live
    assert sent.reduce_only is True
