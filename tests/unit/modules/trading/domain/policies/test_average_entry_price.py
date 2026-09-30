"""`EPIC-028E` — the average entry price of a Spot holding, rebuilt from its
fills by the average-cost method, and `None` whenever the fills do not
explain what is held.

@details Every expected price is worked out in the test's docstring from the
fills themselves, so a reader can check it by hand; each was confirmed by
running the policy (`pitfalls/tests.md` §1).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.average_entry_price import (
    AverageEntryPrice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.average_entry_price import (
    HeldPair,
    average_entry_price,
)

_T0 = datetime(2026, 9, 25, tzinfo=UTC)
_DUST = Decimal("0.00000001")


def _fill(
    minute: int, side: OrderSide, qty: str, price: str, fee: tuple[str, str]
) -> TradeRecord:
    quantity, unit_price = Decimal(qty), Decimal(price)
    return TradeRecord(
        symbol="BTCUSDT",
        trade_id=minute,
        order_id=minute,
        side=side,
        price=unit_price,
        quantity=quantity,
        quote_quantity=quantity * unit_price,
        fee=Decimal(fee[0]),
        fee_asset=fee[1],
        time=_T0 + timedelta(minutes=minute),
    )


def _held(quantity: str) -> HeldPair:
    return HeldPair(
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        held_quantity=Decimal(quantity),
        tolerance=_DUST,
    )


_BUY, _SELL = OrderSide.BUY, OrderSide.SELL


def test_two_buys_average_their_cost_net_of_the_base_fee() -> None:
    """1 BTC at 50 000 and 1 at 60 000, each charged 0.001 BTC: 1.998 BTC
    received for 110 000 USDT, 55 055.055… a coin."""
    fills = [
        _fill(1, _BUY, "1", "50000", ("0.001", "BTC")),
        _fill(2, _BUY, "1", "60000", ("0.001", "BTC")),
    ]

    answer = average_entry_price(fills, _held("1.998"))

    assert answer == AverageEntryPrice(
        symbol="BTCUSDT",
        price=Decimal(110000) / Decimal("1.998"),
        quantity=Decimal("1.998"),
    )


def test_a_fee_in_the_quote_asset_adds_to_what_was_paid() -> None:
    """1 BTC for 50 000 USDT plus a 50 USDT fee: 50 050 a coin."""
    fills = [_fill(1, _BUY, "1", "50000", ("50", "USDT"))]

    answer = average_entry_price(fills, _held("1"))

    assert answer is not None
    assert answer.price == Decimal(50050)


def test_a_fee_in_a_third_asset_is_left_out_of_the_cost() -> None:
    """Paid in BNB: nothing in the fill prices it, so the cost is the quote
    spent alone (the module docstring says so)."""
    fills = [_fill(1, _BUY, "1", "50000", ("0.1", "BNB"))]

    answer = average_entry_price(fills, _held("1"))

    assert answer is not None
    assert answer.price == Decimal(50000)


def test_a_sell_lowers_the_holding_but_not_its_average() -> None:
    """Bought 2 at 50 000 and 1 at 80 000 (average 60 000), sold 1.5: the
    1.5 left still cost 60 000 a coin, whatever the sale fetched."""
    fills = [
        _fill(1, _BUY, "2", "50000", ("0", "BTC")),
        _fill(2, _BUY, "1", "80000", ("0", "BTC")),
        _fill(3, _SELL, "1.5", "90000", ("135", "USDT")),
    ]

    answer = average_entry_price(fills, _held("1.5"))

    assert answer is not None
    assert answer.price == Decimal(60000)
    assert answer.quantity == Decimal("1.5")


def test_fills_are_replayed_oldest_first_whatever_order_they_arrive_in() -> None:
    """The sell of 1 comes last in time: listed first, it would sell coins
    not yet bought and the answer would be `None`."""
    fills = [
        _fill(3, _SELL, "1", "70000", ("0", "USDT")),
        _fill(1, _BUY, "1", "50000", ("0", "BTC")),
        _fill(2, _BUY, "1", "60000", ("0", "BTC")),
    ]

    answer = average_entry_price(fills, _held("1"))

    assert answer is not None
    assert answer.price == Decimal(55000)


def test_coins_the_fills_never_bought_leave_the_price_unknown() -> None:
    """Holds 3 BTC, the window shows 1 bought: 2 came from before `since` or
    a deposit, at a cost nothing here shows."""
    fills = [_fill(1, _BUY, "1", "50000", ("0", "BTC"))]

    assert average_entry_price(fills, _held("3")) is None


def test_selling_more_than_the_fills_bought_leaves_the_price_unknown() -> None:
    fills = [
        _fill(1, _BUY, "1", "50000", ("0", "BTC")),
        _fill(2, _SELL, "2", "60000", ("0", "USDT")),
    ]

    assert average_entry_price(fills, _held("0")) is None


def test_an_oversell_is_not_healed_by_a_later_buy() -> None:
    """Sold 2 of the 1 bought, then bought 2: the replay ends on the 1 BTC
    held, but the oversell already showed coins from outside the fills."""
    fills = [
        _fill(1, _BUY, "1", "50000", ("0", "BTC")),
        _fill(2, _SELL, "2", "60000", ("0", "USDT")),
        _fill(3, _BUY, "2", "60000", ("0", "BTC")),
    ]

    assert average_entry_price(fills, _held("1")) is None


def test_a_holding_sold_out_has_no_average() -> None:
    fills = [
        _fill(1, _BUY, "1", "50000", ("0", "BTC")),
        _fill(2, _SELL, "1", "60000", ("0", "USDT")),
    ]

    assert average_entry_price(fills, _held("0")) is None


def test_no_fills_means_no_average() -> None:
    assert average_entry_price([], _held("1")) is None


def test_a_difference_within_the_dust_tolerance_still_answers() -> None:
    fills = [_fill(1, _BUY, "1", "50000", ("0", "BTC"))]

    assert average_entry_price(fills, _held("1.00000001")) is not None
    assert average_entry_price(fills, _held("1.00000002")) is None
