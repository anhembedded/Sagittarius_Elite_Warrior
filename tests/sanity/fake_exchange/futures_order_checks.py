"""`EPIC-039C` — Binance's refusals of an order before the fake Futures exchange accepts it.

@details A reduce-only order that cannot reduce is `-2022` ("ReduceOnly Order is
rejected"); so is a resting reduce-only order that, with the reduce-only orders already
resting, is for more than the position holds (the error page: it "conflicts with existing
open orders"). A position past what the leverage allows is `-2027` and one past the margin
available is `-2019`. Not in the pages read, and chosen here: the order of the last two
(`-2027` first), and that open orders reserve no margin.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from .futures_account_state import FuturesAccountState
from .futures_market import FuturesMarket, max_notional
from .futures_matching import reduces, remaining
from .futures_symbol_config import FuturesSymbolConfig

_TYPE_MARKET = "MARKET"

#: Binance's refusal of a reduce-only order that would not reduce.
REDUCE_ONLY_REJECTED = (
    400,
    {"code": -2022, "msg": "ReduceOnly Order is rejected."},
)


def _refusal(code: int, message: str) -> tuple[int, dict[str, Any]]:
    return 400, {"code": code, "msg": message}


class OrderChecks:
    """The checks `OrderBookState.place` makes, over the book's resting orders."""

    def __init__(
        self,
        resting: Mapping[str, dict[str, Any]],
        account: FuturesAccountState,
        market: FuturesMarket,
        symbol_config: FuturesSymbolConfig,
    ) -> None:
        self._resting = resting
        self._account = account
        self._market = market
        self._symbol_config = symbol_config

    def refused(self, order: dict[str, Any]) -> tuple[int, dict[str, Any]] | None:
        held = self._account.position_amount(order["symbol"])
        if order["reduceOnly"]:
            if not reduces(held, order["side"]) or self._reduce_only_excess(
                order, held
            ):
                return REDUCE_ONLY_REJECTED
            return None
        return self._margin_refusal(order, held)

    def market_quantity(self, order: dict[str, Any]) -> Decimal:
        """The quantity a market order fills: as asked, or capped at the
        position for a reduce-only one."""
        asked = Decimal(order["origQty"])
        if not order["reduceOnly"]:
            return asked
        return min(asked, abs(self._account.position_amount(order["symbol"])))

    def _reduce_only_excess(self, order: dict[str, Any], held: Decimal) -> bool:
        """A market order is capped instead, not refused."""
        if order["type"] == _TYPE_MARKET:
            return False
        resting = sum(
            (
                remaining(other)
                for other in self._resting.values()
                if other["symbol"] == order["symbol"]
                and other["reduceOnly"]
                and other["side"] == order["side"]
            ),
            Decimal(0),
        )
        return resting + Decimal(order["origQty"]) > abs(held)

    def _margin_refusal(
        self, order: dict[str, Any], held: Decimal
    ) -> tuple[int, dict[str, Any]] | None:
        quantity = Decimal(order["origQty"])
        after = held + (quantity if order["side"] == "BUY" else -quantity)
        if abs(after) <= abs(held):
            return None
        symbol = order["symbol"]
        if order["type"] == _TYPE_MARKET:
            bid, ask = self._market.best_bid_ask(symbol)
            price = ask if order["side"] == "BUY" else bid
        else:
            price = Decimal(order["price"])
        notional = abs(after) * price
        leverage = self._symbol_config.leverage(symbol)
        if notional > max_notional(leverage):
            return _refusal(
                -2027, "Exceeded the maximum allowable position at current leverage."
            )
        needed = notional / leverage - self._account.initial_margin(symbol)
        if needed > self._account.available_balance:
            return _refusal(-2019, "Margin is insufficient.")
        return None
