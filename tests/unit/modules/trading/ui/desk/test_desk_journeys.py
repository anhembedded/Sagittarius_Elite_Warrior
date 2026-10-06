"""`EPIC-028K` — what a user does on a desk, end to end through its
own widgets.

@details The whole desk over verified fakes (`desk_screen_fixtures.py`),
driven by `qtbot` on the order panel's and the tabs' real controls. The
venue's answers are the fakes'; the account events the venue's stream
publishes are emitted on the shared bus, as `VenueEventEmitter` does. The
wire itself (the same orders against the fake exchange, both venues in one
process) is `EPIC-028P`'s and `EPIC-028O`'s integration tests.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLineEdit, QPushButton, QTableView
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .desk_screen_fixtures import Desk, DeskWorld, build_desk
from .order_entry_fixtures import TERMS, spot_status
from .order_entry_presenter_fixtures import canned_preview, placed

SPOT = TradingVenue.SPOT_TESTNET


def _spot_desk(qtbot, world: DeskWorld | None = None) -> Desk:
    return build_desk(
        qtbot,
        SPOT,
        world,
        account_snapshot=FakeAccountSnapshot(spot_status(btc_free=None)),
        order_entry_terms=FakeOrderEntryTerms(TERMS),
    )


def _open_order_ids(desk: Desk) -> list[str]:
    model = desk.view.account_tabs.open_orders_panel.table.model().sourceModel()
    return sorted(row.client_order_id for row in model.rows)


def _held_assets(desk: Desk) -> list[str]:
    model = desk.view.account_tabs.holdings_panel.table.model().sourceModel()
    return sorted(row.asset for row in model.rows)


def _type_buy(qtbot, desk: Desk, *, price: str, amount: str) -> None:
    qtbot.keyClicks(desk.view.findChild(QLineEdit, "txtPriceBuy"), price)
    qtbot.keyClicks(desk.view.findChild(QLineEdit, "txtAmountBuy"), amount)


def test_a_limit_placed_on_the_desk_is_listed_then_cancelled(qtbot) -> None:
    """`EPIC-028K`'s journey. A resting order is announced by the venue's
    stream only when it fills or ends, so the desk lists what the venue
    accepted itself; without that the order sat on the exchange, unseen and
    uncancellable from the desk, until something re-read the account."""
    desk = _spot_desk(qtbot)
    preview = canned_preview(OrderSide.BUY, "0.005", "59000")
    accepted = replace(preview.order, status=OrderStatus.NEW)
    desk.submission.preview_answers(preview)
    desk.submission.submit_answers(placed(accepted))

    _type_buy(qtbot, desk, price="59000", amount="0.005")
    qtbot.mouseClick(
        desk.view.findChild(QPushButton, "btnSubmitBuy"), Qt.MouseButton.LeftButton
    )

    sent = desk.submission.submitted_live[0]
    assert (sent.side, sent.order_type, sent.reference_price) == (
        OrderSide.BUY,
        OrderType.LIMIT,
        Decimal(59000),
    )
    order_id = str(accepted.client_order_id)
    assert _open_order_ids(desk) == [order_id]

    desk.submission.cancel_answers(
        CancelOrderResult(None, replace(accepted, status=OrderStatus.CANCELED))
    )
    table = desk.view.findChild(QTableView, "tblOpenOrders")
    table.selectRow(0)
    desk.view.findChild(QAction, "actCancelOrder").trigger()

    assert desk.submission.cancelled == [("BTCUSDT", order_id)]
    assert _open_order_ids(desk) == []


def _place_buy_answered_new(qtbot, desk: Desk, preview) -> None:
    """Clicks Buy with the venue accepting the order as both trading
    adapters answer: the order unchanged, `NEW`."""
    desk.submission.preview_answers(preview)
    desk.submission.submit_answers(
        placed(replace(preview.order, status=OrderStatus.NEW))
    )
    _type_buy(qtbot, desk, price="59000", amount="0.005")
    qtbot.mouseClick(
        desk.view.findChild(QPushButton, "btnSubmitBuy"), Qt.MouseButton.LeftButton
    )


def _fill(world: DeskWorld, preview) -> None:
    world.bus.emit(
        OrderFilledEvent(
            order=replace(preview.order, status=OrderStatus.FILLED),
            fill_price=Decimal(59000),
            fill_quantity=Decimal("0.005"),
            venue=SPOT,
        )
    )


def test_a_fill_reported_before_the_acceptance_leaves_nothing_open(qtbot, qapp) -> None:
    """The PR #308 review, blocking: the fill (the venue's stream) and the
    acceptance (the REST answer) reach the UI thread in either order. A
    fill first used to leave the filled order listed as open by the late
    `NEW`."""
    world = DeskWorld()
    desk = _spot_desk(qtbot, world)
    preview = canned_preview(OrderSide.BUY, "0.005", "59000")
    _fill(world, preview)
    qapp.processEvents()

    _place_buy_answered_new(qtbot, desk, preview)

    assert desk.submission.submitted_live
    assert _open_order_ids(desk) == []


def test_a_fill_reported_after_the_acceptance_removes_the_row(qtbot, qapp) -> None:
    world = DeskWorld()
    desk = _spot_desk(qtbot, world)
    preview = canned_preview(OrderSide.BUY, "0.005", "59000")
    _place_buy_answered_new(qtbot, desk, preview)
    assert _open_order_ids(desk) == [str(preview.order.client_order_id)]

    _fill(world, preview)
    qapp.processEvents()

    assert _open_order_ids(desk) == []
