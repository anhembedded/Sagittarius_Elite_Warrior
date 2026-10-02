"""`EPIC-028L` — the Spot desk's journey: Buy, then Assets shows the holding.

@details The whole Spot desk over verified fakes (`desk_screen_fixtures.py`),
driven by `qtbot` on the order panel's real controls; the venue's balance
update is emitted on the shared bus as `SpotUserDataStream` publishes it.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QPushButton
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.holdings_changed_event import (
    HoldingsChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
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


def _held_assets(desk: Desk) -> list[str]:
    model = desk.view.account_tabs.holdings_panel.table.model().sourceModel()
    return sorted(row.asset for row in model.rows)


def test_a_spot_buy_shows_the_bought_asset_in_assets(qtbot, qapp) -> None:
    world = DeskWorld()
    desk = build_desk(
        qtbot,
        SPOT,
        world,
        account_snapshot=FakeAccountSnapshot(spot_status(btc_free=None)),
        order_entry_terms=FakeOrderEntryTerms(TERMS),
    )
    assert _held_assets(desk) == ["USDT"]
    preview = canned_preview(OrderSide.BUY, "0.005", "59000")
    desk.submission.preview_answers(preview)
    desk.submission.submit_answers(
        placed(replace(preview.order, status=OrderStatus.FILLED))
    )

    qtbot.keyClicks(desk.view.findChild(QLineEdit, "txtPriceBuy"), "59000")
    qtbot.keyClicks(desk.view.findChild(QLineEdit, "txtAmountBuy"), "0.005")
    qtbot.mouseClick(
        desk.view.findChild(QPushButton, "btnSubmitBuy"), Qt.MouseButton.LeftButton
    )
    world.bus.emit(
        HoldingsChangedEvent(
            holdings=(
                SpotHolding("USDT", Decimal(705), Decimal(0), Decimal("0.01")),
                SpotHolding("BTC", Decimal("0.005"), Decimal(0), Decimal("0.00001")),
            ),
            venue=SPOT,
        )
    )
    qapp.processEvents()

    assert desk.submission.submitted_live[0].side is OrderSide.BUY
    assert _held_assets(desk) == ["BTC", "USDT"]
