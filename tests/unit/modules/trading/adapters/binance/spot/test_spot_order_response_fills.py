"""`BOT-173` — the fills a Spot placement response carries."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_order_response_fills import (
    response_fills,
)


def _entry(**changes: Any) -> dict[str, Any]:
    base = {
        "price": "2500.00",
        "qty": "0.00400000",
        "commission": "0.00000400",
        "commissionAsset": "ETH",
        "tradeId": 31415,
    }
    return base | changes


def test_a_full_response_gives_one_fill_per_trade_with_its_id_and_fee() -> None:
    found = response_fills({"fills": [_entry(), _entry(tradeId=31416, qty="0.1")]})

    assert [fill.trade_id for fill in found.fills] == [31415, 31416]
    assert found.fills[0].price == Decimal("2500.00")
    assert found.fills[0].quantity == Decimal("0.004")
    assert found.fills[0].fee == (Decimal("0.000004"), "ETH")
    assert found.unreadable == 0


def test_a_response_without_fills_gives_none() -> None:
    assert response_fills({"status": "NEW"}).fills == ()
    assert response_fills({"fills": []}).fills == ()


def test_a_fill_with_no_trade_id_is_not_countable_and_is_reported_as_left_out() -> None:
    entry = _entry()
    del entry["tradeId"]

    found = response_fills({"fills": [entry, _entry(tradeId=-1), _entry(tradeId="x")]})

    assert found.fills == ()
    assert found.unreadable == 3


def test_a_fill_with_no_commission_has_no_fee_rather_than_a_zero_one() -> None:
    entry = _entry()
    del entry["commission"]

    (fill,) = response_fills({"fills": [entry]}).fills

    assert fill.fee is None
