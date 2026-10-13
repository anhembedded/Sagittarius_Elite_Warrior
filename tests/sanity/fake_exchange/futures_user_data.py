"""`EPIC-039C` — the user-data events the fake Futures exchange queues.

@details Shapes follow Binance's `ORDER_TRADE_UPDATE` example and field list and its
`ACCOUNT_UPDATE` page (read 2026-10-13): single-letter keys, numbers as strings, the
transaction time `T` and event time `E` on the exchange's clock. The fake has no websocket
(`stream_transport.py`): events wait in a queue a test world drains into the stream
adapter, as the Spot fake's `drain_user_data_events()` does.

Chosen here, not stated by the pages read: `er` (expiry reason) is a string; an order
update carries no `N`/`n` unless it carries a commission; `cw` (cross wallet) is the
wallet less the isolated margins.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .futures_account_state import FuturesAccountState
from .futures_faults import MatchFaults
from .history_log import now_ms

ORDER_TRADE_UPDATE = "ORDER_TRADE_UPDATE"
ACCOUNT_UPDATE = "ACCOUNT_UPDATE"
#: Expiry reasons (`er`): a reduce-only order knocked out, and an order on an account
#: that was liquidated.
EXPIRED_REDUCE_ONLY = "4"
EXPIRED_LIQUIDATION = "5"


def _q(value: Decimal) -> str:
    return f"{value:.8f}"


def order_update(
    order: dict[str, Any],
    *,
    execution: str,
    status: str,
    trade: dict[str, Any] | None = None,
    expiry_reason: str | None = None,
) -> dict[str, Any]:
    """One `ORDER_TRADE_UPDATE`. `trade` is `{qty, price, commission, realized,
    trade_id, maker}` for a fill."""
    at = now_ms()
    body: dict[str, Any] = {
        "s": order["symbol"],
        "c": order["clientOrderId"],
        "S": order["side"],
        "o": order["type"],
        "f": order["timeInForce"],
        "q": order["origQty"],
        "p": order["price"],
        "ap": order["avgPrice"] if trade else "0",
        "sp": order["stopPrice"],
        "x": execution,
        "X": status,
        "i": order["orderId"],
        "l": "0",
        "z": order["executedQty"],
        "L": "0",
        "T": at,
        "t": 0,
        "b": "0",
        "a": "0",
        "m": False,
        "R": order["reduceOnly"],
        "wt": "CONTRACT_PRICE",
        "ot": order["type"],
        "ps": order["positionSide"],
        "cp": False,
        "rp": "0",
    }
    if trade is not None:
        body.update(
            l=str(trade["qty"]),
            L=str(trade["price"]),
            t=trade["trade_id"],
            m=trade["maker"],
            rp=_q(trade["realized"]),
        )
        if trade["commission"] > 0:
            body.update(N="USDT", n=_q(trade["commission"]))
    if expiry_reason is not None:
        body["er"] = expiry_reason
    return {"e": ORDER_TRADE_UPDATE, "T": at, "E": at, "o": body}


def position_row(
    symbol: str,
    amount: Decimal,
    entry: Decimal,
    unrealized: Decimal,
    isolated_wallet: Decimal | None,
) -> dict[str, str]:
    """One `"P"` entry of an `ACCOUNT_UPDATE`; `isolated_wallet` is `None` under cross."""
    return {
        "s": symbol,
        "pa": _q(amount),
        "ep": _q(entry),
        "bep": _q(entry),
        "cr": "0.00000000",
        "up": _q(unrealized),
        "mt": "cross" if isolated_wallet is None else "isolated",
        "iw": _q(isolated_wallet or Decimal(0)),
        "ps": "BOTH",
    }


def account_update(
    reason: str,
    *,
    wallet: Decimal,
    cross_wallet: Decimal,
    balance_change: Decimal,
    positions: list[dict[str, str]],
    symbol: str | None = None,
) -> dict[str, Any]:
    at = now_ms()
    body: dict[str, Any] = {
        "m": reason,
        "B": [
            {
                "a": "USDT",
                "wb": _q(wallet),
                "cw": _q(cross_wallet),
                "bc": _q(balance_change),
            }
        ],
        "P": positions,
    }
    if symbol is not None:
        body["S"] = symbol
    return {"e": ACCOUNT_UPDATE, "T": at, "E": at, "a": body}


class UserDataQueue:
    """The events waiting for a test world to drain them into the stream adapter."""

    def __init__(self, account: FuturesAccountState, faults: MatchFaults) -> None:
        self._account = account
        self._faults = faults
        self._events: list[dict[str, Any]] = []

    def publish(self, event: dict[str, Any]) -> None:
        self._events.append(event)
        is_fill = event["e"] == ORDER_TRADE_UPDATE and event["o"]["x"] == "TRADE"
        if is_fill and self._faults.duplicate_reports:
            self._events.append(dict(event))

    def drain(self) -> list[dict[str, Any]]:
        events, self._events = self._events, []
        return events

    def publish_account_update(
        self,
        reason: str,
        symbol: str,
        balance_change: Decimal,
        *,
        with_position: bool = True,
    ) -> None:
        positions = []
        if with_position:
            held = self._account.positions.amount(symbol)
            positions = [
                position_row(
                    symbol,
                    held,
                    self._account.positions.entry_price(symbol) if held else Decimal(0),
                    self._account.positions.unrealized(symbol),
                    self._account.positions.isolated_margin(symbol),
                )
            ]
        self.publish(
            account_update(
                reason,
                wallet=self._account.wallet_balance,
                cross_wallet=self._account.cross_wallet,
                balance_change=balance_change,
                positions=positions,
                symbol=symbol if reason == "FUNDING_FEE" else None,
            )
        )
