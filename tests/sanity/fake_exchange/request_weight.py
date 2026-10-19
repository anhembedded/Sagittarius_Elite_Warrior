"""`BUG-216` — the request weight the Futures fake charges each request, as Binance documents it.

@details The exchange limits an IP by weight per minute (2,400 on USDⓈ-M Futures), not by request
count, and a request's weight depends on its path and, for two of them, on whether `symbol` is
given. `WeightMeter` records every request with its weight, so a test can say what a journey cost
and which path spent it; `used_in_minute` is the figure the exchange returns in
`X-MBX-USED-WEIGHT-1M`, which the app's own rate-limit policy reads.

The table is the Futures one (`/fapi/`); a path it does not list weighs 1, as a new endpoint
without a documented weight would be assumed to. Orders weigh 0 on the IP window (they count
against the order-rate limit, a different budget).
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

#: Weight of a path whatever its parameters.
_FIXED: dict[tuple[str, str], int] = {
    ("GET", "/fapi/v1/time"): 1,
    ("GET", "/fapi/v1/ping"): 1,
    ("GET", "/fapi/v1/exchangeInfo"): 1,
    ("GET", "/fapi/v1/klines"): 1,
    ("GET", "/fapi/v2/account"): 5,
    ("GET", "/fapi/v3/positionRisk"): 5,
    ("GET", "/fapi/v1/positionSide/dual"): 30,
    ("GET", "/fapi/v1/multiAssetsMargin"): 30,
    ("GET", "/fapi/v1/allOrders"): 5,
    ("GET", "/fapi/v1/allAlgoOrders"): 5,
    ("GET", "/fapi/v1/userTrades"): 5,
    ("GET", "/fapi/v1/income"): 30,
    ("GET", "/fapi/v1/algoOrder"): 1,
    ("GET", "/fapi/v1/commissionRate"): 20,
    ("GET", "/fapi/v1/symbolConfig"): 5,
    ("GET", "/fapi/v1/leverageBracket"): 1,
    ("POST", "/fapi/v1/order"): 0,
    ("POST", "/fapi/v1/order/test"): 1,
    ("POST", "/fapi/v1/algoOrder"): 0,
}
#: Paths that weigh `(with symbol, without symbol)`.
_BY_SYMBOL: dict[tuple[str, str], tuple[int, int]] = {
    ("GET", "/fapi/v1/openOrders"): (1, 40),
    ("GET", "/fapi/v1/openAlgoOrders"): (1, 40),
    ("GET", "/fapi/v1/premiumIndex"): (1, 10),
    ("GET", "/fapi/v1/ticker/bookTicker"): (2, 5),
}
_DEFAULT_WEIGHT = 1
_SECONDS_PER_MINUTE = 60


def request_weight(method: str, path: str, params: dict[str, str]) -> int:
    """The weight Binance charges one request."""
    key = (method, path)
    if key in _BY_SYMBOL:
        with_symbol, without = _BY_SYMBOL[key]
        return with_symbol if params.get("symbol") else without
    return _FIXED.get(key, _DEFAULT_WEIGHT)


@dataclass(frozen=True)
class MeteredRequest:
    method: str
    path: str
    weight: int
    #: Whether the request named a symbol (`openOrders` and two more weigh by it).
    with_symbol: bool
    #: Which minute of the meter's clock it fell in.
    minute: int


class WeightMeter:
    """Every request the fake answered, with its weight."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._requests: list[MeteredRequest] = []

    def use_clock(self, clock: Callable[[], float]) -> None:
        """Count minutes by `clock` from now on (`BUG-232`): a test that states "inside one minute"
        holds the clock still, so the wall clock's calendar minute cannot roll over mid-test and
        reset the weight the app's gate reads, as Binance's own window does at its edge."""
        self._clock = clock

    def charge(self, method: str, path: str, params: dict[str, str]) -> int:
        """Record one request; @return the weight used in the current minute, itself included."""
        minute = int(self._clock() // _SECONDS_PER_MINUTE)
        request = MeteredRequest(
            method,
            path,
            request_weight(method, path, params),
            bool(params.get("symbol")),
            minute,
        )
        with self._lock:
            self._requests.append(request)
            return sum(r.weight for r in self._requests if r.minute == minute)

    @property
    def requests(self) -> tuple[MeteredRequest, ...]:
        with self._lock:
            return tuple(self._requests)

    @property
    def total(self) -> int:
        return sum(r.weight for r in self.requests)

    def mark(self) -> int:
        """A position in the record, to measure what happens after it with `since`."""
        return len(self.requests)

    def since(self, mark: int) -> tuple[MeteredRequest, ...]:
        return self.requests[mark:]

    def by_path_since(self, mark: int) -> Counter[str]:
        """Weight spent per `METHOD path` after `mark`, the answer to "what spent it"."""
        spent: Counter[str] = Counter()
        for request in self.since(mark):
            spent[f"{request.method} {request.path}"] += request.weight
        return spent

    def weight_since(self, mark: int) -> int:
        return sum(r.weight for r in self.since(mark))
