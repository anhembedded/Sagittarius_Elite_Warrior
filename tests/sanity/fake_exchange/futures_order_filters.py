"""`EPIC-037E` — the symbol filters Binance applies to an order, read from the fake's own
`exchangeInfo` (`futures_listing.py`).

@details Sources: the USDⓈ-M error-code page (read 2026-10-20) gives `-4014` "Price not increased
by tick size.", `-4023` "Qty not increased by step size.", `-4003` "Quantity less than zero.",
`-4005` "Quantity greater than max quantity.", `-1111` "Precision is over the maximum defined for
this asset." and `-4164` "Order's notional must be no smaller than N (unless you choose reduce
only)". A price outside `minPrice`/`maxPrice` is not on that page: it answers `-1013` "Filter
failure: PRICE_FILTER", the shape the app's own translator reads (`binance_error_translator.py`)
and the owner's Spot log showed (`BUG-147`). `minQty` is not checked on its own: in the fake's
table it equals `stepSize`, so a quantity under it is `0` (`-4003`) or off the step. The order of the checks (precision, then step, then size) is chosen here.
Not modelled yet: `PERCENT_PRICE` (the fake's `exchangeInfo` does not advertise it, and the app's
Futures parser does not read it: `CS-007`), and the filters of a conditional (algo) order.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .futures_listing import FUTURES_EXCHANGE_INFO

_TYPE_MARKET = "MARKET"


def _refusal(code: int, message: str) -> tuple[int, dict[str, Any]]:
    return 400, {"code": code, "msg": message}


def _decimals(value: Decimal) -> int:
    return max(0, -int(value.normalize().as_tuple().exponent))


@dataclass(frozen=True)
class SymbolFilters:
    """One symbol's row of `exchangeInfo`, as numbers."""

    price_precision: int
    quantity_precision: int
    tick_size: Decimal
    min_price: Decimal
    max_price: Decimal
    step_size: Decimal
    max_qty: Decimal
    min_notional: Decimal

    @classmethod
    def parse(cls, row: Mapping[str, Any]) -> SymbolFilters:
        by_type = {entry["filterType"]: entry for entry in row["filters"]}
        price, lot = by_type["PRICE_FILTER"], by_type["LOT_SIZE"]
        return cls(
            price_precision=int(row["pricePrecision"]),
            quantity_precision=int(row["quantityPrecision"]),
            tick_size=Decimal(price["tickSize"]),
            min_price=Decimal(price["minPrice"]),
            max_price=Decimal(price["maxPrice"]),
            step_size=Decimal(lot["stepSize"]),
            max_qty=Decimal(lot["maxQty"]),
            min_notional=Decimal(by_type["MIN_NOTIONAL"]["notional"]),
        )


class OrderFilters:
    """The filter checks `OrderChecks.refused` makes, per listed symbol."""

    def __init__(self, reference_price: Callable[[str, str], Decimal]) -> None:
        #: `(symbol, side) -> the price a market order would trade at`, for its notional.
        self._reference_price = reference_price
        self._by_symbol = {
            row["symbol"]: SymbolFilters.parse(row)
            for row in FUTURES_EXCHANGE_INFO["symbols"]
        }

    def refused(self, order: dict[str, Any]) -> tuple[int, dict[str, Any]] | None:
        rules = self._by_symbol.get(order["symbol"])
        if rules is None:
            return None  # an unlisted symbol is `-1121`'s business, not a filter's
        quantity = Decimal(order["origQty"])
        market = order["type"] == _TYPE_MARKET
        price = None if market else Decimal(order["price"])
        return (
            self._quantity_refusal(rules, quantity)
            or (None if price is None else self._price_refusal(rules, price))
            or self._notional_refusal(order, rules, quantity, price)
        )

    def _quantity_refusal(
        self, rules: SymbolFilters, quantity: Decimal
    ) -> tuple[int, dict[str, Any]] | None:
        if quantity <= 0:
            return _refusal(-4003, "Quantity less than zero.")
        if _decimals(quantity) > rules.quantity_precision:
            return _refusal(
                -1111, "Precision is over the maximum defined for this asset."
            )
        if quantity % rules.step_size != 0:
            return _refusal(-4023, "Qty not increased by step size.")
        if quantity > rules.max_qty:
            return _refusal(-4005, "Quantity greater than max quantity.")
        return None

    def _price_refusal(
        self, rules: SymbolFilters, price: Decimal
    ) -> tuple[int, dict[str, Any]] | None:
        if _decimals(price) > rules.price_precision:
            return _refusal(
                -1111, "Precision is over the maximum defined for this asset."
            )
        if price % rules.tick_size != 0:
            return _refusal(-4014, "Price not increased by tick size.")
        if price < rules.min_price:
            return _refusal(-4013, "Price less than min price.")
        if price > rules.max_price:
            return _refusal(-4002, "Price greater than max price.")
        return None

    def _notional_refusal(
        self,
        order: dict[str, Any],
        rules: SymbolFilters,
        quantity: Decimal,
        price: Decimal | None,
    ) -> tuple[int, dict[str, Any]] | None:
        if order["reduceOnly"]:
            return None
        at = price or self._reference_price(order["symbol"], order["side"])
        if quantity * at < rules.min_notional:
            return _refusal(
                -4164,
                f"Order's notional must be no smaller than {rules.min_notional} "
                "(unless you choose reduce only)",
            )
        return None
