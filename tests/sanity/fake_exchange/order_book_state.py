"""`EPIC-021J` §2.1 — the fake Futures account's orders. A resting order
placed appears in `open_orders()`; canceled, it does not.

`EPIC-028E` — every accepted order is also remembered in `history`, with a
real timestamp, for `GET /fapi/v1/allOrders`.

`EPIC-028O` — a `MARKET` order fills at once against the book
(`futures_account_state.py`): it answers `FILLED`, never rests, is remembered
as filled, books one trade for `GET /fapi/v1/userTrades` and moves the
position and wallet `positionRisk` and `account` report. A reduce-only order
that would open or add to a position is refused with Binance's `-2022`; one
larger than the position closes it, reporting the capped fill in
`executedQty` while `origQty` stays what was sent.

`EPIC-028R` — conditional orders live apart, in `algo` (Binance's Algo Order
API); `move_price` triggers the ones a price crosses, placing their regular
orders here.

`EPIC-039C` — this is now a matching engine for resting orders. `move_price` moves the
market and makes every `LIMIT` order the price crosses trade, at its own limit price (a
buy at or below, a sell at or above), partly if the test caps the fill; a limit placed
already marketable rests until the next move, as in the Spot fake. A fill pays the maker
fee. The rest of what a real account does follows from the fill: reduce-only orders that
can no longer reduce expire, a mark through the liquidation price closes the position,
`advance_clock` settles funding. Every order change and fill is queued as the user-data
event Binance would push (`drain_user_data_events`, `futures_user_data.py`), and the book
can be made unfair (`faults`, `futures_faults.py`). The rules, with the pages they come
from and what is chosen here, are in the test files that pin them
(`tests/unit/fake_exchange/test_fake_futures_*.py`).
"""

from __future__ import annotations

import itertools
from decimal import Decimal
from typing import Any

from . import futures_liquidation, futures_user_data
from .futures_account_settings import AccountSettings
from .futures_account_state import MAKER_FEE_RATE, FuturesAccountState, FuturesFill
from .futures_algo_orders import FuturesAlgoOrders
from .futures_faults import MatchFaults
from .futures_funding import FuturesFunding
from .futures_market import FuturesMarket
from .futures_matching import crosses, reduces, remaining
from .futures_order_checks import OrderChecks
from .futures_symbol_config import FuturesSymbolConfig
from .history_log import HistoryLog, now_ms

_STATUS_NEW = "NEW"
_STATUS_PARTIAL = "PARTIALLY_FILLED"
_STATUS_CANCELED = "CANCELED"
_STATUS_EXPIRED = "EXPIRED"
_STATUS_FILLED = "FILLED"
_TYPE_MARKET = "MARKET"
_TYPE_LIQUIDATION = "LIQUIDATION"


class OrderBookState:
    """One instance per `run_binance_fake_server()` call — state does not
    outlive a single test's `with` block."""

    def __init__(self) -> None:
        self._orders: dict[str, dict[str, Any]] = {}
        self._next_order_id = 1_000_000
        self.history = HistoryLog()
        #: `EPIC-028F` — the account's leverage and margin mode per symbol,
        #: carried here because this is the one state the Futures routes get.
        self.symbol_config = FuturesSymbolConfig()
        #: `EPIC-039C` — the funding clock and rates, and the prices a test moves.
        self.funding = FuturesFunding()
        self.market = FuturesMarket(self.funding)
        #: `EPIC-028O` — the wallet and positions market fills move.
        self.account = FuturesAccountState(self.symbol_config, self.market)
        self._trade_ids = itertools.count(5_000_000)
        #: `EPIC-028R` — the account's conditional orders.
        self.algo = FuturesAlgoOrders(
            self.account.positions.amount,
            self._publish_algo_update,
            lambda: self._next_order_id,
        )
        #: `EPIC-039C` — late, duplicated and rejected (all off).
        self.faults = MatchFaults()
        self._events = futures_user_data.UserDataQueue(self.account, self.faults)
        self._checks = OrderChecks(
            self._orders, self.account, self.market, self.symbol_config
        )
        self._settings = AccountSettings(
            self._orders, self.algo, self.account, self.symbol_config
        )
        self._forced_ids = itertools.count(1)

    def _take_order_id(self) -> int:
        self._next_order_id += 1
        return self._next_order_id - 1

    def _publish_algo_update(self, algo: dict[str, Any], placed: str | None) -> None:
        self._events.publish(
            futures_user_data.algo_update(algo, placed_order_id=placed)
        )

    # -- the market ---------------------------------------------------------

    def move_price(
        self, symbol: str, price: Decimal, *, fill_at_most: Decimal | None = None
    ) -> None:
        """The market trades at `price`: it becomes the mark, every resting order it
        crosses trades (at most `fill_at_most` of each, when given), every conditional
        order it crosses triggers (`EPIC-028R`; the orders it places rest until the next
        move, like any limit placed marketable), and a position it liquidates closes."""
        self.market.set_mark_price(symbol, price)
        if not self.faults.hold_fills:
            self._match(symbol, price, fill_at_most)
        self.algo.trigger(symbol, price, self.place)
        self._liquidate_if_crossed(symbol)

    def release_fills(self) -> None:
        """Fills what the latest prices cross: the fills `faults.hold_fills` delayed."""
        for symbol in {order["symbol"] for order in self._orders.values()}:
            self._match(symbol, self.market.mark_price(symbol), None)

    def set_funding_rate(self, symbol: str, rate: Decimal) -> None:
        self.funding.set_rate(symbol, rate)

    def advance_clock(self, milliseconds: int) -> None:
        """Moves the funding clock; every settlement it passes charges (or credits)
        each open position at the mark and queues the `ACCOUNT_UPDATE` Binance pushes; a
        position that funding leaves past its liquidation price is liquidated."""
        for _settled_at in self.funding.advance(milliseconds):
            for symbol in self.account.positions.symbols():
                self._settle_funding(symbol)
        # Funding paid out of an isolated margin can carry the position past its
        # liquidation price at the mark it already stands at.
        for symbol in self.account.positions.symbols():
            self._liquidate_if_crossed(symbol)

    def drain_user_data_events(self) -> list[dict[str, Any]]:
        """Returns and clears every user-data event queued since the last drain."""
        return self._events.drain()

    # -- orders -------------------------------------------------------------

    def place(self, params: dict[str, str]) -> tuple[int, dict[str, Any]]:
        """@brief Accepts one order from `POST /fapi/v1/order`'s
        form-encoded params: a `MARKET` order fills, anything else rests.
        @return `(status, body)`: the acknowledgement, or Binance's refusal."""
        rejected = self.faults.take_rejection()
        if rejected is not None:
            return rejected
        client_order_id = params["newClientOrderId"]
        order = {
            "orderId": self._take_order_id(),
            "symbol": params["symbol"],
            "status": _STATUS_NEW,
            "clientOrderId": client_order_id,
            "price": params.get("price", "0"),
            "avgPrice": "0",
            "origQty": params["quantity"],
            "executedQty": "0",
            "cumQuote": "0",
            "type": params["type"],
            "side": params["side"],
            "positionSide": params.get("positionSide", "BOTH"),
            "stopPrice": params.get("stopPrice", "0"),
            "timeInForce": params.get("timeInForce", "GTC"),
            "reduceOnly": str(params.get("reduceOnly", "False")).lower() == "true",
        }
        refused = self._checks.refused(order)
        if refused is not None:
            return refused
        placed_at = now_ms()
        self.history.remember_order(
            {**order, "time": placed_at, "updateTime": placed_at}
        )
        self._events.publish(
            futures_user_data.order_update(order, execution="NEW", status=_STATUS_NEW)
        )
        if order["type"] == _TYPE_MARKET:
            quantity = self._checks.market_quantity(order)
            fill = self.account.fill_market(order["symbol"], order["side"], quantity)
            self._record_fill(order, fill)
            self._after_position_change(order["symbol"])
            return 200, {**order}
        self._orders[client_order_id] = order
        return 200, order

    def cancel(
        self, symbol: str, client_order_id: str | None, order_id: str | None
    ) -> dict[str, Any] | None:
        """@brief Removes and returns the matching order, or `None` if
        nothing open matches — the caller turns that into Binance's real
        `-2011 Unknown order sent` shape, not this module's job."""
        match_id = client_order_id
        if match_id is None and order_id is not None:
            match_id = next(
                (
                    cid
                    for cid, order in self._orders.items()
                    if str(order["orderId"]) == str(order_id)
                ),
                None,
            )
        order = self._orders.get(match_id) if match_id else None
        if order is None or order["symbol"] != symbol:
            return None
        del self._orders[match_id]
        self.faults.note_cancelled(match_id, order)
        self.history.mark_canceled(match_id)
        self._events.publish(
            futures_user_data.order_update(
                order, execution=_STATUS_CANCELED, status=_STATUS_CANCELED
            )
        )
        return {**order, "status": _STATUS_CANCELED}

    def cancel_all(self, symbol: str) -> None:
        for client_order_id in [
            cid for cid, order in self._orders.items() if order["symbol"] == symbol
        ]:
            self.cancel(symbol, client_order_id, None)

    def open_orders(self, symbol: str | None) -> list[dict[str, Any]]:
        listed = [*self._orders.values(), *self.faults.lagging_orders()]
        return [o for o in listed if symbol is None or o["symbol"] == symbol]

    # -- account settings ---------------------------------------------------

    def change_leverage(self, params: dict[str, str]) -> tuple[int, object]:
        return self._settings.change_leverage(params)

    def change_margin_type(self, params: dict[str, str]) -> tuple[int, object]:
        return self._settings.change_margin_type(params)

    def position_mode(self, params: dict[str, str]) -> tuple[int, object]:
        return self._settings.position_mode(params)

    def set_position_mode(self, params: dict[str, str]) -> tuple[int, object]:
        return self._settings.set_position_mode(params)

    # -- matching -----------------------------------------------------------

    def _match(self, symbol: str, price: Decimal, fill_at_most: Decimal | None) -> None:
        for order in list(self._orders.values()):
            if order["symbol"] == symbol and crosses(order, price):
                self._trade_resting(order, fill_at_most)

    def _trade_resting(
        self, order: dict[str, Any], fill_at_most: Decimal | None
    ) -> None:
        symbol = order["symbol"]
        quantity = remaining(order)
        if fill_at_most is not None:
            quantity = min(quantity, fill_at_most)
        if order["reduceOnly"]:
            held = self.account.positions.amount(symbol)
            if not reduces(held, order["side"]):
                self._expire(order, futures_user_data.EXPIRED_REDUCE_ONLY)
                return
            quantity = min(quantity, abs(held))
        fill = self.account.fill_at(
            symbol, order["side"], quantity, Decimal(order["price"]), MAKER_FEE_RATE
        )
        self._record_fill(order, fill)
        if (
            order["reduceOnly"]
            and order["status"] != _STATUS_FILLED
            and self.account.positions.amount(symbol) == 0
        ):
            self._expire(order, futures_user_data.EXPIRED_REDUCE_ONLY)
        self._after_position_change(symbol)

    def _after_position_change(self, symbol: str) -> None:
        """A reduce-only order that can no longer reduce is knocked out (reason 4)."""
        self.algo.after_position_change(symbol)
        held = self.account.positions.amount(symbol)
        for order in list(self._orders.values()):
            if (
                order["symbol"] == symbol
                and order["reduceOnly"]
                and not reduces(held, order["side"])
            ):
                self._expire(order, futures_user_data.EXPIRED_REDUCE_ONLY)

    def _expire(self, order: dict[str, Any], reason: str) -> None:
        self._orders.pop(order["clientOrderId"], None)
        order["status"] = _STATUS_EXPIRED
        self.history.update_order(order["clientOrderId"], status=_STATUS_EXPIRED)
        self._events.publish(
            futures_user_data.order_update(
                order,
                execution=_STATUS_EXPIRED,
                status=_STATUS_EXPIRED,
                expiry_reason=reason,
            )
        )

    def _record_fill(self, order: dict[str, Any], fill: FuturesFill) -> None:
        """Books one fill of `order`: its totals, the trade row, and the events."""
        first = Decimal(order["executedQty"]) == 0
        executed = Decimal(order["executedQty"]) + fill.quantity
        quote = fill.price * fill.quantity
        if not first:
            quote += Decimal(order["cumQuote"])
        complete = order["type"] == _TYPE_MARKET or executed >= Decimal(
            order["origQty"]
        )
        order.update(
            status=_STATUS_FILLED if complete else _STATUS_PARTIAL,
            executedQty=str(executed),
            avgPrice=str(fill.price),
            cumQuote=str(quote),
        )
        self.history.update_order(
            order["clientOrderId"],
            status=order["status"],
            executedQty=order["executedQty"],
            avgPrice=order["avgPrice"],
            cumQuote=order["cumQuote"],
        )
        if complete:
            self._orders.pop(order["clientOrderId"], None)
        maker = order["type"] != _TYPE_MARKET and order["type"] != _TYPE_LIQUIDATION
        trade_id = next(self._trade_ids)
        self.history.remember_trade(fill.as_trade_row(order, trade_id, maker, now_ms()))
        self._events.publish(
            futures_user_data.order_update(
                order,
                execution="TRADE",
                status=order["status"],
                trade={
                    "qty": fill.quantity,
                    "price": fill.price,
                    "commission": fill.commission,
                    "realized": fill.realized_pnl,
                    "trade_id": trade_id,
                    "maker": maker,
                },
            )
        )
        self._events.publish_account_update("ORDER", order["symbol"], Decimal(0))

    # -- liquidation and funding ---------------------------------------------

    def _liquidate_if_crossed(self, symbol: str) -> None:
        held = self.account.positions.amount(symbol)
        price = self.account.positions.liquidation_price(
            symbol, self.account.wallet_balance
        )
        if held == 0 or price is None:
            return
        if not futures_liquidation.is_liquidated(
            held, self.market.mark_price(symbol), price
        ):
            return
        for order in [o for o in self._orders.values() if o["symbol"] == symbol]:
            self._expire(order, futures_user_data.EXPIRED_LIQUIDATION)
        self.algo.cancel_all(symbol)
        forced = self._forced_order(symbol, held, price)
        self._events.publish(
            futures_user_data.order_update(
                forced, execution="CALCULATED", status=_STATUS_NEW
            )
        )
        self._record_fill(forced, self.account.liquidate(symbol, price))

    def _settle_funding(self, symbol: str) -> None:
        payment = self.account.apply_funding(symbol, self.funding.rate(symbol))
        if payment is None:
            return
        self.history.remember_income(
            {
                "symbol": symbol,
                "incomeType": "FUNDING_FEE",
                "income": f"{payment:.8f}",
                "asset": "USDT",
                "time": now_ms(),
                "info": "FUNDING_FEE",
                "tranId": next(self._trade_ids),
                "tradeId": "",
            }
        )
        isolated = self.account.positions.isolated(symbol)
        self._events.publish_account_update(
            "FUNDING_FEE", symbol, payment, with_position=isolated
        )

    def _forced_order(
        self, symbol: str, held: Decimal, price: Decimal
    ) -> dict[str, Any]:
        order = futures_liquidation.forced_order(
            self._take_order_id(), next(self._forced_ids), symbol, held, price
        )
        placed_at = now_ms()
        self.history.remember_order(
            {**order, "time": placed_at, "updateTime": placed_at}
        )
        return order
