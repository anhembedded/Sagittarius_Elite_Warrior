"""`EPIC-028O` — the fake Futures market's fixed prices and leverage
brackets: what `premiumIndex`, `ticker/bookTicker` and `leverageBracket`
answer.

@details One bracket table for every symbol, shaped like Binance's
`BTCUSDT` table: leverage falls and the maintenance-margin rate rises with
the notional, and each `cum` is the previous one plus the floor times the
rate step, so the table is internally consistent. Leverage 10 allows up to
10 000 000 USDT, the figure `POST /fapi/v1/leverage` has always answered for
it. Prices start fixed per symbol and a test moves them (`FuturesMarket`, `EPIC-039C`);
the book is one tick either side of the mark, and a market order fills against it
(`futures_account_state.py`). Shapes per Binance's documented USD-M API.
"""

from __future__ import annotations

from decimal import Decimal

from .futures_funding import FuturesFunding

#: `(bracket, initialLeverage, notionalFloor, notionalCap, maintMarginRatio,
#: cum)`.
BRACKETS: tuple[tuple[int, int, int, int, str, str], ...] = (
    (1, 125, 0, 50_000, "0.004", "0"),
    (2, 100, 50_000, 500_000, "0.005", "50"),
    (3, 50, 500_000, 2_000_000, "0.01", "2550"),
    (4, 10, 2_000_000, 10_000_000, "0.025", "32550"),
    (5, 5, 10_000_000, 50_000_000, "0.05", "282550"),
)

#: `symbol -> (mark price, tick size)`; the ticks match `exchangeInfo`.
_MARKS: dict[str, tuple[Decimal, Decimal]] = {
    "BTCUSDT": (Decimal("64000.0"), Decimal("0.1")),
    "ETHUSDT": (Decimal("3200.00"), Decimal("0.01")),
}

#: The symbols the fake Futures market lists.
LISTED_SYMBOLS = frozenset(_MARKS)

#: Binance's answer for a symbol it does not list.
INVALID_SYMBOL = (400, {"code": -1121, "msg": "Invalid symbol."})


def max_notional(leverage: int) -> Decimal:
    """The largest notional `leverage` allows: the highest cap among the
    brackets whose initial leverage is at least `leverage`."""
    return Decimal(max(row[3] for row in BRACKETS if row[1] >= leverage))


def leverage_bracket(symbol: str) -> tuple[int, object]:
    if symbol not in _MARKS:
        return INVALID_SYMBOL
    return 200, {
        "symbol": symbol,
        "notionalCoef": 1.0,
        "brackets": [
            {
                "bracket": bracket,
                "initialLeverage": leverage,
                "notionalCap": cap,
                "notionalFloor": floor,
                "maintMarginRatio": float(ratio),
                "cum": float(cum),
            }
            for bracket, leverage, floor, cap, ratio, cum in BRACKETS
        ],
    }


class FuturesMarket:
    """`EPIC-039C` — the fake market's prices, which a test can move.

    @details Every listed symbol starts at its fixed mark, the book one tick either
    side of it, so a fake nobody moved answers what it always answered.
    `set_mark_price` moves the one price the mark, the index and the book are made of
    (the fake has a mark price and no separate last price).
    """

    def __init__(self, funding: FuturesFunding) -> None:
        self._marks = {symbol: mark for symbol, (mark, _) in _MARKS.items()}
        self._funding = funding

    def mark_price(self, symbol: str) -> Decimal:
        return self._marks[symbol]

    def set_mark_price(self, symbol: str, price: Decimal) -> None:
        if symbol in self._marks:
            self._marks[symbol] = price

    def best_bid_ask(self, symbol: str) -> tuple[Decimal, Decimal]:
        """`(bid, ask)`: one tick either side of the mark, what a market sell and
        buy fill at."""
        tick = _MARKS[symbol][1]
        mark = self._marks[symbol]
        return mark - tick, mark + tick

    def premium_index(self, symbol: str) -> tuple[int, object]:
        if symbol not in _MARKS:
            return INVALID_SYMBOL
        mark = self._marks[symbol]
        return 200, {
            "symbol": symbol,
            "markPrice": str(mark),
            "indexPrice": str(mark),
            "estimatedSettlePrice": str(mark),
            "lastFundingRate": f"{self._funding.rate(symbol):.8f}",
            "interestRate": "0.00010000",
            "nextFundingTime": self._funding.next_time_ms,
            "time": self._funding.now_ms,
        }

    def book_ticker(self, symbol: str) -> tuple[int, object]:
        if symbol not in _MARKS:
            return INVALID_SYMBOL
        bid, ask = self.best_bid_ask(symbol)
        return 200, {
            "symbol": symbol,
            "bidPrice": str(bid),
            "bidQty": "2.500",
            "askPrice": str(ask),
            "askQty": "1.750",
            "time": self._funding.now_ms,
        }
