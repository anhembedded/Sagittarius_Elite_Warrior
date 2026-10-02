"""`EPIC-028M` — the Dev Board's F9 dialog is the desks' order panel: an
order placed there is announced for the board's Open orders, a refusal is
said in the operator's own words, the board's price reaches the panel only
from the venue's own market, and a Futures entry with TP/SL is protected once
it fills.

@details Verified fakes behind every port, the real `OrderFeed` on the
engine's `MemoryEventBus`, a recorded "Yes" for the dialog and a worker pool
that runs inline (the desks' own fixtures).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
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
from Sagittarius_Elite_Warrior.src.modules.trading.ui.dashboard.dev_board_order_entry import (
    DevBoardOrderEntry,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.execute_order_block_reason import (
    format_execute_order_block_reason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_feed import OrderFeed
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

from ..desk.futures_entry_fixtures import MARK, futures_status, futures_terms
from ..desk.order_entry_fixtures import SYMBOL, TERMS, InlineThreadManager, spot_status
from ..desk.order_entry_presenter_fixtures import Answers, canned_preview, placed

SPOT = TradingVenue.SPOT_TESTNET
FUTURES = TradingVenue.FUTURES_TESTNET


@dataclass
class Board:
    entry: DevBoardOrderEntry
    submission: FakeOrderSubmission
    bus: MemoryEventBus
    accepted: list[Order]
    log: list[str]


def _board(qapp, venue: TradingVenue) -> Board:
    submission = FakeOrderSubmission()
    futures = venue is FUTURES
    ports = fake_venue_ports(
        venue,
        order_submission=submission,
        account_snapshot=FakeAccountSnapshot(
            futures_status() if futures else spot_status()
        ),
        order_entry_terms=futures_terms() if futures else FakeOrderEntryTerms(TERMS),
    )
    bus = MemoryEventBus()
    feed = OrderFeed(bus, venue)
    log: list[str] = []
    entry = DevBoardOrderEntry(
        ports, InlineThreadManager(), Answers(True), feed, log.append
    )
    feed.setParent(entry)
    accepted: list[Order] = []
    entry.orderAccepted.connect(accepted.append)
    entry.show_symbol(SYMBOL)
    return Board(entry, submission, bus, accepted, log)


def _type_limit_buy(board: Board, quantity: str, price: str) -> Order:
    vm = board.entry.view_model
    vm.set_order_type(OrderType.LIMIT)
    vm.set_price(EntrySide.BUY, price)
    vm.set_quantity(EntrySide.BUY, quantity)
    preview = canned_preview(OrderSide.BUY, quantity, price)
    board.submission.preview_answers(preview)
    board.submission.submit_answers(placed(preview.order))
    return preview.order


def test_the_dialog_shows_the_boards_venue_with_its_desks_profile(qapp) -> None:
    board = _board(qapp, SPOT)

    assert board.entry.view_model.profile.venue is SPOT
    assert board.entry.view_model.order_symbol == SYMBOL


def test_an_order_placed_on_the_board_is_announced_for_its_open_orders(
    qapp,
) -> None:
    """The venue's stream announces an order only when it fills or ends: a
    resting Limit placed from the board joins Open orders from this answer
    (the gap `EPIC-028K` found on the desks, closed here for the board)."""
    board = _board(qapp, SPOT)
    sent = _type_limit_buy(board, "1", "100")

    board.entry.view_model.request_submit(EntrySide.BUY)

    (live,) = board.submission.submitted_live
    assert live.side is OrderSide.BUY
    assert board.accepted == [sent]


def test_a_leased_symbol_is_refused_in_the_operators_own_words(qapp) -> None:
    """Carried from the board's manual-order card (`PRO-003` §4.1.2, moved
    onto the order path in `EPIC-025` PR 2.1f): a symbol an armed strategy
    holds refuses a hand-placed order, and the refusal names why."""
    board = _board(qapp, SPOT)
    _type_limit_buy(board, "1", "100")
    board.submission.submit_answers(
        ExecuteOrderResult(ExecuteOrderSafetyGate.SYMBOL_LEASED, None, (), None)
    )

    board.entry.view_model.request_submit(EntrySide.BUY)

    vm = board.entry.view_model
    assert vm.message_is_error
    assert format_execute_order_block_reason(ExecuteOrderSafetyGate.SYMBOL_LEASED) in (
        vm.message
    )
    assert board.accepted == []


def test_the_boards_price_counts_only_from_the_venues_market(qapp) -> None:
    """The board may chart Spot while it trades Futures: a Spot close is not
    the price a Futures order fills at."""
    board = _board(qapp, FUTURES)

    board.entry.update_last_price(MarketType.SPOT, Decimal(1))
    assert board.entry.view_model.last_price is None

    board.entry.update_last_price(MarketType.FUTURES_USD_M, MARK)
    assert board.entry.view_model.last_price == MARK


def test_a_futures_entry_with_tp_sl_is_protected_once_it_fills(qapp) -> None:
    board = _board(qapp, FUTURES)
    board.entry.update_last_price(MarketType.FUTURES_USD_M, MARK)
    options = board.entry.view_model.options
    options.set_tp_sl_enabled(True)
    options.set_take_profit(EntrySide.BUY, "63000")
    options.set_stop_loss(EntrySide.BUY, "58000")
    sent = _type_limit_buy(board, "0.005", "60000")
    board.entry.view_model.request_submit(EntrySide.BUY)
    assert len(board.submission.submitted_live) == 1  # the entry alone

    board.bus.emit(
        OrderFilledEvent(
            order=replace(sent, status=OrderStatus.FILLED),
            fill_price=Decimal(60000),
            fill_quantity=sent.quantity,
            venue=FUTURES,
        )
    )
    qapp.processEvents()

    protective = board.submission.submitted_live[1:]
    assert {request.side for request in protective} == {OrderSide.SELL}
    assert all(request.reduce_only for request in protective)
    assert len(protective) == 2  # take-profit and stop-loss
