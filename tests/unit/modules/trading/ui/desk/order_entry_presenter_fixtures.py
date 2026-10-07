"""`EPIC-028H` — the order-panel presenter under test: verified fakes for
every port, a recorded confirmation dialog, and canned previews, shared by
the presenter's test files."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_confirmation import (
    OrderConfirmation,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_presenter import (
    OrderEntryPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_view_model import (
    OrderEntryViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.venue_key import (
    KeyCheck,
    always_keyed,
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

SPOT = TradingVenue.SPOT_TESTNET


@dataclass
class Answers:
    """What the confirmation dialog is asked, and what it answers."""

    answer: bool = True
    asked: list[OrderConfirmation] = field(default_factory=list)

    def __call__(self, confirmation: OrderConfirmation) -> bool:
        self.asked.append(confirmation)
        return self.answer


@dataclass
class PresentedPanel:
    vm: OrderEntryViewModel
    presenter: OrderEntryPresenter
    submission: FakeOrderSubmission
    account: FakeAccountSnapshot
    terms: FakeOrderEntryTerms
    confirm: Answers


def presented_panel(
    *,
    threads: InlineThreadManager | HeldThreadManager | None = None,
    account: FakeAccountSnapshot | None = None,
    answer: bool = True,
    books: dict[str, BestBidAsk] | None = None,
    has_key: KeyCheck = always_keyed,
) -> PresentedPanel:
    submission = FakeOrderSubmission()
    account = account or FakeAccountSnapshot(spot_status())
    terms = FakeOrderEntryTerms(TERMS, books=books)
    ports = fake_venue_ports(
        SPOT,
        order_submission=submission,
        account_snapshot=account,
        order_entry_terms=terms,
    )
    vm = OrderEntryViewModel(desk_profile_for(SPOT))
    confirm = Answers(answer)
    presenter = OrderEntryPresenter(
        vm, ports, threads or InlineThreadManager(), confirm, has_key=has_key
    )
    return PresentedPanel(vm, presenter, submission, account, terms, confirm)


def canned_preview(side: OrderSide, quantity: str, price: str | None) -> OrderPreview:
    order = Order(
        client_order_id=generate_client_order_id(),
        symbol=SYMBOL,
        side=side,
        order_type=OrderType.LIMIT if price else OrderType.MARKET,
        quantity=Decimal(quantity),
        price=None if price is None else Decimal(price),
    )
    return OrderPreview(
        order=order,
        raw_quantity=Decimal(quantity),
        estimated_notional=Decimal(quantity) * Decimal(price or "100"),
        min_notional=Decimal(10),
        step_size=Decimal("0.001"),
        notional_check=NotionalCheck.SUFFICIENT,
    )


def placed(order: Order) -> ExecuteOrderResult:
    return ExecuteOrderResult(
        blocked_by=None, preview=None, limit_checks=(), submitted_order=order
    )
