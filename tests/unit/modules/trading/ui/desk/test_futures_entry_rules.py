"""`EPIC-028I` — a Futures side's figures: the maximum Binance's cost
lets the balance pay within the leverage's cap (and, for a market order, the
open loss against the book), reduce-only sized by the position, the cost
and the liquidation estimate, and TP/SL checked against the price."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_order_estimates import (
    FuturesOrderTerms,
    futures_max_quantity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.futures_entry_rules import (
    futures_side_figures,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_rules import (
    EntrySide,
    SideInput,
)

from .futures_entry_fixtures import MARK, futures_context, futures_reads
from .order_entry_fixtures import STEP, TAKER

_BUY = EntrySide.BUY
_SELL = EntrySide.SELL
_LIMIT = OrderType.LIMIT
_MARKET = OrderType.MARKET
_PRICE = Decimal(60000)


def _entry(quantity: str | None = None, **changes: object) -> SideInput:
    entry = SideInput(
        price=_PRICE, quantity=Decimal(quantity) if quantity is not None else None
    )
    return replace(entry, **changes)


def _terms(side: OrderSide, order_price: Decimal | None) -> FuturesOrderTerms:
    return FuturesOrderTerms(
        side=side,
        order_price=order_price,
        last_price=MARK,
        mark_price=MARK,
        leverage=10,
        fee_rate=TAKER,
        notional_headroom=Decimal(1_000_000),
    )


def test_a_limit_long_is_sized_by_binances_cost_at_its_leverage() -> None:
    figures = futures_side_figures(_BUY, _LIMIT, _entry(), futures_context(), MARK)

    assert figures.max_quantity == futures_max_quantity(
        Decimal(1000), _terms(OrderSide.BUY, _PRICE), STEP
    )
    assert figures.available_asset == "USDT"
    assert figures.problem == "Enter an amount."


@pytest.mark.parametrize(
    ("side", "against", "beside"),
    [
        # A long meets the ask: an ask above the mark is an open loss, a bid
        # below it is nothing to a long.
        (_BUY, (MARK - 1, MARK + 300), (MARK - 300, MARK + 1)),
        # A short meets the bid: a bid below the mark is its open loss.
        (_SELL, (MARK - 300, MARK + 1), (MARK - 1, MARK + 300)),
    ],
    ids=["long-meets-the-ask", "short-meets-the-bid"],
)
def test_a_market_maximum_pays_the_open_loss_on_its_own_side_of_the_book(
    side: EntrySide,
    against: tuple[Decimal, Decimal],
    beside: tuple[Decimal, Decimal],
) -> None:
    def market_max(bid: Decimal, ask: Decimal) -> Decimal | None:
        book = BestBidAsk("BTCUSDT", bid, Decimal(1), ask, Decimal(1))
        context = futures_context(Decimal(10_000), futures_reads(book=book))
        return futures_side_figures(side, _MARKET, _entry(), context, MARK).max_quantity

    costly = market_max(*against)
    cheap = market_max(*beside)

    assert costly is not None and cheap is not None
    assert costly < cheap


def test_a_market_order_waits_for_the_book() -> None:
    empty = BestBidAsk("BTCUSDT", Decimal(0), Decimal(0), Decimal(0), Decimal(0))
    context = futures_context(reads=futures_reads(book=empty))

    figures = futures_side_figures(_BUY, _MARKET, _entry("0.01"), context, MARK)

    assert figures.max_quantity is None
    assert figures.problem == "The order book could not be read yet."


def test_the_position_already_open_uses_up_the_leverages_cap() -> None:
    reads = futures_reads(max_notional=Decimal(120000), position=Decimal("1.5"))

    figures = futures_side_figures(
        _BUY, _LIMIT, _entry(), futures_context(Decimal(10**6), reads), MARK
    )

    # 120 000 cap − 1.5 × 60 000 open = 30 000 of headroom: 0.5 BTC.
    assert figures.max_quantity == Decimal("0.5")


def test_more_than_the_margin_pays_is_refused_with_the_maximum() -> None:
    figures = futures_side_figures(_BUY, _LIMIT, _entry("5"), futures_context(), MARK)

    assert figures.problem is not None
    assert figures.problem.startswith("Not enough margin: at most")


def test_an_opening_order_shows_its_cost_and_liquidation_estimate() -> None:
    figures = futures_side_figures(_BUY, _LIMIT, _entry("0.1"), futures_context(), MARK)

    assert figures.problem is None
    assert figures.cost == Decimal("0.1") * _PRICE / 10
    assert figures.liquidation is not None
    assert figures.liquidation.is_estimate
    assert figures.liquidation.price is not None
    assert figures.liquidation.price < _PRICE


def test_isolated_margin_liquidates_closer_than_a_full_cross_wallet() -> None:
    cross = futures_side_figures(_BUY, _LIMIT, _entry("0.1"), futures_context(), MARK)
    isolated_reads = futures_reads(margin_type=MarginType.ISOLATED)
    isolated = futures_side_figures(
        _BUY, _LIMIT, _entry("0.1"), futures_context(reads=isolated_reads), MARK
    )

    assert cross.liquidation is not None and isolated.liquidation is not None
    assert cross.liquidation.price is not None
    assert isolated.liquidation.price is not None
    assert isolated.liquidation.price > cross.liquidation.price


def test_a_cross_position_without_a_wallet_read_has_no_estimate() -> None:
    reads = futures_reads(wallet=None)

    figures = futures_side_figures(
        _BUY, _LIMIT, _entry("0.1"), futures_context(reads=reads), MARK
    )

    assert figures.liquidation is None


@pytest.mark.parametrize(
    ("side", "position", "maximum", "problem"),
    [
        (_SELL, Decimal("0.02"), Decimal("0.02"), None),
        (_BUY, Decimal("-0.02"), Decimal("0.02"), None),
        (_BUY, Decimal("0.02"), Decimal(0), "No short position to reduce."),
        (_SELL, Decimal(0), Decimal(0), "No long position to reduce."),
    ],
    ids=["sell-reduces-long", "buy-reduces-short", "buy-on-long", "sell-when-flat"],
)
def test_reduce_only_is_sized_by_the_position_it_reduces(
    side: EntrySide, position: Decimal, maximum: Decimal, problem: str | None
) -> None:
    context = futures_context(reads=futures_reads(position=position))

    figures = futures_side_figures(
        side, _LIMIT, _entry("0.02", reduce_only=True), context, MARK
    )

    assert figures.max_quantity == maximum
    assert figures.problem == problem
    assert figures.cost == 0
    assert figures.liquidation is None


def test_reduce_only_cannot_reduce_more_than_the_position() -> None:
    context = futures_context(reads=futures_reads(position=Decimal("0.02")))

    figures = futures_side_figures(
        _SELL, _LIMIT, _entry("0.05", reduce_only=True), context, MARK
    )

    assert figures.problem == "Reduce-only: the long position is 0.02."


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"take_profit": Decimal(59000)}, "take-profit must be above"),
        ({"stop_loss": Decimal(61000)}, "stop-loss must be below"),
        (
            {"take_profit": Decimal(63000), "reduce_only": True},
            "turn off reduce-only",
        ),
    ],
)
def test_tp_and_sl_are_checked_against_the_orders_price(
    changes: dict[str, object], problem: str
) -> None:
    context = futures_context(reads=futures_reads(position=Decimal("-0.5")))

    figures = futures_side_figures(_BUY, _LIMIT, _entry("0.01"), context, MARK)
    checked = futures_side_figures(
        _BUY, _LIMIT, _entry("0.01", **changes), context, MARK
    )

    assert figures.problem is None or "reduce" in figures.problem
    assert checked.problem is not None
    assert problem in checked.problem


def test_well_placed_tp_and_sl_leave_the_order_sendable() -> None:
    figures = futures_side_figures(
        _BUY,
        _LIMIT,
        _entry("0.01", take_profit=Decimal(63000), stop_loss=Decimal(58000)),
        futures_context(),
        MARK,
    )

    assert figures.problem is None


def test_a_desk_whose_reads_failed_says_so_rather_than_sizing() -> None:
    context = replace(futures_context(), futures=None)

    figures = futures_side_figures(_BUY, _LIMIT, _entry("0.01"), context, MARK)

    assert figures.max_quantity is None
    assert figures.problem == "Leverage and margin are still loading."
