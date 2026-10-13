"""`EPIC-039C` — where the fake Futures exchange liquidates a one-way position.

@details Binance's one-way formula for a single position
(`LP = (WB + cum - side x Q x EP) / (Q x MMR - side x Q)`), with `WB` the isolated margin
(or the wallet balance under cross), `cum` and `MMR` the maintenance amount and rate of the
bracket the position's notional falls in. It is written out again here on purpose: the
production estimate (`trading/contracts/liquidation_estimate.py`) is what the app trusts,
and a fake that imported it could never disagree with it.
`test_the_fakes_liquidation_price_is_the_production_estimate` is where the two meet.

A long is liquidated when the mark falls to its price, a short when the mark rises to it.
Brackets come from the fake's own table (`futures_market.BRACKETS`).
"""

from __future__ import annotations

from decimal import Decimal

from .futures_market import BRACKETS


def maintenance_terms(notional: Decimal) -> tuple[Decimal, Decimal]:
    """`(maintenance rate, cum)` of the bracket `notional` falls in; the last bracket
    for anything above the table."""
    for _, _, floor, cap, rate, cum in BRACKETS:
        if floor <= notional < cap:
            return Decimal(rate), Decimal(cum)
    *_, rate, cum = BRACKETS[-1]
    return Decimal(rate), Decimal(cum)


def maintenance_margin(notional: Decimal) -> Decimal:
    rate, cum = maintenance_terms(notional)
    return notional * rate - cum


def liquidation_price(
    amount: Decimal, entry: Decimal, margin: Decimal
) -> Decimal | None:
    """The price that liquidates `amount` (signed) opened at `entry` with `margin`
    behind it; `None` when no price does."""
    side = 1 if amount > 0 else -1
    quantity = abs(amount)
    rate, cum = maintenance_terms(quantity * entry)
    price = (margin + cum - side * quantity * entry) / (
        quantity * rate - side * quantity
    )
    return price if price > 0 else None


def is_liquidated(amount: Decimal, mark: Decimal, price: Decimal) -> bool:
    return mark <= price if amount > 0 else mark >= price


def forced_order(
    order_id: int, number: int, symbol: str, held: Decimal, price: Decimal
) -> dict[str, object]:
    """The order the exchange itself places to close `held`: client order id
    `autoclose-<n>`, type `LIQUIDATION` (the order-update page)."""
    return {
        "orderId": order_id,
        "symbol": symbol,
        "status": "NEW",
        "clientOrderId": f"autoclose-{number}",
        "price": str(price),
        "avgPrice": "0",
        "origQty": str(abs(held)),
        "executedQty": "0",
        "cumQuote": "0",
        "type": "LIQUIDATION",
        "side": "SELL" if held > 0 else "BUY",
        "positionSide": "BOTH",
        "stopPrice": "0",
        "timeInForce": "IOC",
        "reduceOnly": False,
    }
