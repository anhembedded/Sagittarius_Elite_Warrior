"""`EPIC-027J` §3 — the one piece of mutable state the fake exchange keeps
for Spot: balances and open orders. A second, independent state object
beside `OrderBookState` (Futures) — Spot and Futures accounts are
different facts, never a union of both.

Deliberately a minimal matching engine, not a real one: a `MARKET` order
fills immediately, in full, at one fixed per-symbol reference price (no
order book, no partial fills, no slippage) — enough to exercise a filled
order's balance movement (`EPIC-027J`'s own acceptance criterion) without
a second implementation of Binance's real engine to maintain
(`order_book_state.py`'s own reasoning, extended only as far as this
task requires). A `LIMIT` order is stored open (`NEW`) in `SpotOrderBook`
and fills when a test moves the last price across it (`EPIC-029A`).

`EPIC-028O` — a test moves a symbol's last price with `set_last_price`.
A `STOP_LOSS_LIMIT` the new price crosses (a buy stop at or below it, a
sell stop at or above it) is triggered; once triggered it fills, in full
at its own limit price, as soon as that limit is marketable at the last
price (a buy limit at or above it, a sell limit at or below it). A market
order fills at the current last price, and a market buy may be sized by
`quoteOrderQty`: it buys as much as the quote amount pays for, truncated
to 8 decimals.

Fee convention ("fee in the received asset", this task's own acceptance
criterion): a BUY receives the base asset, so its fee is charged in the
base asset; a SELL receives the quote asset, so its fee is charged in the
quote asset — matching Binance's real spot commission behaviour.

Payload shapes (response bodies, `executionReport`/`outboundAccountPosition`
field names) are taken from `python-binance`'s own `create_order()`
docstring (`FULL` response, its own doc source cites
https://developers.binance.com/docs/binance-spot-api-docs/rest-api/trading-endpoints#new-order-trade)
and Binance's public Spot User Data Streams documentation
(`Payload: Execution Report` / `Payload: Account Update`), not guessed.

`EPIC-028E` — every accepted order and every fill is also remembered in
`history`, with a real timestamp, for `GET /api/v3/allOrders` and
`GET /api/v3/myTrades` (row shape from Binance's documented `myTrades`).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any

from .history_log import HistoryLog, now_ms
from .spot_order_book import SpotOrderBook

_STATUS_NEW = "NEW"
_STATUS_FILLED = "FILLED"
_STATUS_CANCELED = "CANCELED"

_SIDE_BUY = "BUY"
_ORDER_TYPE_MARKET = "MARKET"
_ORDER_TYPE_STOP_LIMIT = "STOP_LOSS_LIMIT"
#: `EPIC-029A` (`BUG-141`) — the prefix of the id a cancel request is given
#: when it names none, as Binance gives one; the report's `"c"`.
_CANCEL_ID_PREFIX = "fakecxl"

#: symbol -> (base asset, quote asset, fixed reference price used to
#: "fill" a MARKET order). Matches the two symbols `spot_routes.py`'s own
#: `exchangeInfo` fixture advertises.
_SYMBOLS: dict[str, tuple[str, str, Decimal]] = {
    "BTCUSDT": ("BTC", "USDT", Decimal(50000)),
    "ETHUSDT": ("ETH", "USDT", Decimal(3000)),
}

#: Binance's real spot base commission rate (`EPIC-027`'s own README §1.1
#: measured this as the default rate the fee simulator already assumes).
_FEE_RATE = Decimal("0.001")

_EIGHT_DP = Decimal("0.00000001")


def _q(value: Decimal) -> str:
    """Formats a `Decimal` the way Binance's own JSON numeric fields are
    shaped: a fixed-point string, truncated (never rounded up past what
    was actually credited/debited) to 8 decimal places."""
    return str(value.quantize(_EIGHT_DP, rounding=ROUND_DOWN))


@dataclass(frozen=True)
class _Fill:
    price: Decimal
    qty: Decimal
    quote_amount: Decimal
    commission: Decimal
    commission_asset: str
    #: The exchange's id of this trade: the history lists it as `id`, and the
    #: stream's executionReport carries it as `"t"`, so a client can count the
    #: fill once however it learned of it.
    trade_id: int


class _Balance:
    __slots__ = ("free", "locked")

    def __init__(self, free: Decimal) -> None:
        self.free = free
        self.locked = Decimal(0)


class SpotAccountState:
    """One instance per `run_binance_fake_server()` call — like
    `OrderBookState`, state does not outlive a single test's `with`
    block."""

    def __init__(self) -> None:
        self._book = SpotOrderBook()
        self._order_ids = itertools.count(2_000_000)
        self._cancel_ids = itertools.count(1)
        self._balances: dict[str, _Balance] = {
            "USDT": _Balance(Decimal(100000)),
            "BTC": _Balance(Decimal(10)),
            "ETH": _Balance(Decimal(100)),
        }
        self._user_data_events: list[dict[str, Any]] = []
        self._trade_ids = itertools.count(3_000_000)
        self.history = HistoryLog()
        #: `EPIC-028O` — each symbol's last price: what a market order fills
        #: at and what a stop-limit is triggered by.
        self._last_prices = {
            symbol: price for symbol, (_, _, price) in _SYMBOLS.items()
        }

    def place(self, params: dict[str, str]) -> dict[str, Any]:
        """@brief Places one order from `POST /api/v3/order`'s form-encoded
        params and returns Binance's `FULL` response shape (always — this
        fixture has no `newOrderRespType` distinction to preserve)."""
        symbol = params["symbol"]
        side = params["side"]
        order_type = params["type"]
        quantity = self._quantity(symbol, params)
        client_order_id = params["newClientOrderId"]
        order_id = next(self._order_ids)

        fill = (
            self._fill(symbol, side, quantity, self._last_prices[symbol])
            if order_type == _ORDER_TYPE_MARKET
            else None
        )

        order: dict[str, Any] = {
            "symbol": symbol,
            "orderId": order_id,
            "clientOrderId": client_order_id,
            "transactTime": 0,
            "price": params.get("price", "0.00000000"),
            "origQty": _q(quantity),
            "executedQty": _q(fill.qty) if fill else "0.00000000",
            "cummulativeQuoteQty": _q(fill.quote_amount) if fill else "0.00000000",
            "status": _STATUS_FILLED if fill else _STATUS_NEW,
            "timeInForce": params.get("timeInForce", "GTC"),
            "type": order_type,
            "side": side,
            "fills": [self._fill_entry(fill)] if fill else [],
        }
        if order_type == _ORDER_TYPE_STOP_LIMIT:
            order["stopPrice"] = params["stopPrice"]
        if fill is None:
            self._book.rest(order, order_id)
        else:
            self._emit_fill_events(order, fill)
        self._remember(order, fill)
        return order

    def _remember(self, order: dict[str, Any], fill: _Fill | None) -> None:
        placed_at = now_ms()
        self.history.remember_order(
            {
                key: value
                for key, value in order.items()
                if key not in {"fills", "transactTime"}
            }
            | {"time": placed_at, "updateTime": placed_at}
        )
        if fill is not None:
            self._remember_trade(order, fill, placed_at)

    def _remember_trade(self, order: dict[str, Any], fill: _Fill, at_ms: int) -> None:
        self.history.remember_trade(
            {
                "symbol": order["symbol"],
                "id": fill.trade_id,
                "orderId": order["orderId"],
                "orderListId": -1,
                "price": _q(fill.price),
                "qty": _q(fill.qty),
                "quoteQty": _q(fill.quote_amount),
                "commission": _q(fill.commission),
                "commissionAsset": fill.commission_asset,
                "time": at_ms,
                "isBuyer": order["side"] == _SIDE_BUY,
                "isMaker": False,
                "isBestMatch": True,
            }
        )

    def cancel(
        self, symbol: str, client_order_id: str | None, order_id: str | None
    ) -> dict[str, Any] | None:
        """@brief Removes and returns the matching open order, or `None` if
        nothing open matches — the caller turns that into Binance's real
        `-2011 Unknown order sent` shape, not this module's job. A filled
        `MARKET` order was never stored here, so it is correctly
        uncancellable, same as real Binance."""
        order = self._book.take(symbol, client_order_id, order_id)
        if order is None:
            return None
        self.history.mark_canceled(order["clientOrderId"])
        self._emit_cancel_report(order)
        return {
            "symbol": order["symbol"],
            "origClientOrderId": order["clientOrderId"],
            "orderId": order["_order_id"],
            "clientOrderId": order["clientOrderId"],
            "price": order["price"],
            "origQty": order["origQty"],
            "executedQty": order["executedQty"],
            "cummulativeQuoteQty": order["cummulativeQuoteQty"],
            "status": _STATUS_CANCELED,
            "timeInForce": order["timeInForce"],
            "type": order["type"],
            "side": order["side"],
        }

    def cancel_all(self, symbol: str) -> list[dict[str, Any]]:
        """@brief Cancels every open order on `symbol`. Real Binance's own
        `DELETE /api/v3/openOrders` answers a *list* of canceled orders —
        a different shape from Futures' plain message dict, verified by
        reading Binance's documented response for this exact endpoint."""
        canceled = [
            self.cancel(symbol, order["clientOrderId"], None)
            for order in self._book.resting(symbol)
        ]
        return [order for order in canceled if order is not None]

    def open_orders(self, symbol: str | None) -> list[dict[str, Any]]:
        return [
            {key: value for key, value in order.items() if not key.startswith("_")}
            for order in self._book.resting(symbol)
        ]

    def free_balance(self, asset: str) -> Decimal:
        return self._balances[asset].free

    def withdraw_free(self, asset: str, amount: Decimal) -> None:
        """The user moves or sells `amount` of `asset` by hand, outside any bot."""
        self._balances[asset].free -= amount

    def account_balances(self) -> list[dict[str, str]]:
        return [
            {"asset": asset, "free": _q(balance.free), "locked": _q(balance.locked)}
            for asset, balance in self._balances.items()
        ]

    def drain_user_data_events(self) -> list[dict[str, Any]]:
        """@brief Returns and clears every user-data event queued by a fill
        since the last drain. There is no live WebSocket push in this HTTP
        fixture (`EPIC-021J`'s own scope never included one) — a test that
        needs to observe a fill's user-data shape reads this directly, the
        same "white-box test of the fixture itself" the futures side's own
        `OrderBookState` is exercised through."""
        events, self._user_data_events = self._user_data_events, []
        return events

    def last_price(self, symbol: str) -> Decimal | None:
        """@brief `EPIC-028O` — the price a market order fills at, which
        both ticker routes quote. @return `None` for a symbol the fake does
        not list."""
        return self._last_prices.get(symbol)

    def set_last_price(self, symbol: str, price: Decimal) -> None:
        """@brief `EPIC-028O` — moves `symbol`'s last price and fills every
        resting order the move makes trade (`SpotOrderBook.trade_at`)."""
        self._last_prices[symbol] = price
        for order, trade_price in self._book.trade_at(symbol, price):
            self._fill_resting(order, trade_price)

    def _fill_resting(self, order: dict[str, Any], price: Decimal) -> None:
        fill = self._fill(
            order["symbol"], order["side"], Decimal(order["origQty"]), price
        )
        filled = {
            key: value for key, value in order.items() if not key.startswith("_")
        } | {
            "orderId": order["_order_id"],
            "status": _STATUS_FILLED,
            "executedQty": _q(fill.qty),
            "cummulativeQuoteQty": _q(fill.quote_amount),
        }
        self._emit_fill_events(filled, fill)
        self.history.mark_filled(
            order["clientOrderId"], _q(fill.qty), _q(fill.quote_amount)
        )
        self._remember_trade(filled, fill, now_ms())

    def _quantity(self, symbol: str, params: dict[str, str]) -> Decimal:
        """The base quantity, or, for a market buy sized by `quoteOrderQty`,
        what that amount buys at the last price (truncated to 8 decimals)."""
        if "quoteOrderQty" in params:
            spend = Decimal(params["quoteOrderQty"])
            return (spend / self._last_prices[symbol]).quantize(
                _EIGHT_DP, rounding=ROUND_DOWN
            )
        return Decimal(params["quantity"])

    def _fill(self, symbol: str, side: str, quantity: Decimal, price: Decimal) -> _Fill:
        base_asset, quote_asset, _ = _SYMBOLS[symbol]
        quote_amount = quantity * price
        if side == _SIDE_BUY:
            commission = quantity * _FEE_RATE
            commission_asset = base_asset
            self._balances[quote_asset].free -= quote_amount
            self._balances[base_asset].free += quantity - commission
        else:
            commission = quote_amount * _FEE_RATE
            commission_asset = quote_asset
            self._balances[base_asset].free -= quantity
            self._balances[quote_asset].free += quote_amount - commission
        return _Fill(
            price=price,
            qty=quantity,
            quote_amount=quote_amount,
            commission=commission,
            commission_asset=commission_asset,
            trade_id=next(self._trade_ids),
        )

    def _fill_entry(self, fill: _Fill) -> dict[str, str]:
        return {
            "price": _q(fill.price),
            "qty": _q(fill.qty),
            "commission": _q(fill.commission),
            "commissionAsset": fill.commission_asset,
        }

    def _emit_cancel_report(self, order: dict[str, Any]) -> None:
        """A cancel's executionReport: `"c"` names the cancel request, `"C"`
        the order, as on the real venue (`BUG-141`)."""
        self._user_data_events.append(
            {
                "e": "executionReport",
                "s": order["symbol"],
                "c": f"{_CANCEL_ID_PREFIX}{next(self._cancel_ids)}",
                "C": order["clientOrderId"],
                "S": order["side"],
                "o": order["type"],
                "x": _STATUS_CANCELED,
                "X": _STATUS_CANCELED,
                "i": order["_order_id"],
                "q": order["origQty"],
                "p": order["price"],
                "z": order["executedQty"],
                "T": 0,
            }
        )

    def _emit_fill_events(self, order: dict[str, Any], fill: _Fill) -> None:
        base_asset, quote_asset, _ = _SYMBOLS[order["symbol"]]
        self._user_data_events.append(
            {
                "e": "executionReport",
                "E": 0,
                "s": order["symbol"],
                "c": order["clientOrderId"],
                "S": order["side"],
                "o": order["type"],
                "x": "TRADE",
                "X": _STATUS_FILLED,
                "i": order["orderId"],
                "q": order["origQty"],
                "l": _q(fill.qty),
                "L": _q(fill.price),
                "t": fill.trade_id,
                "z": _q(fill.qty),
                "n": _q(fill.commission),
                "N": fill.commission_asset,
                "T": 0,
            }
        )
        self._user_data_events.append(
            {
                "e": "outboundAccountPosition",
                "E": 0,
                "u": 0,
                "B": [
                    {
                        "a": asset,
                        "f": _q(self._balances[asset].free),
                        "l": _q(self._balances[asset].locked),
                    }
                    for asset in (base_asset, quote_asset)
                ],
            }
        )
