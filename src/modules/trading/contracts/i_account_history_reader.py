"""`EPIC-028E` — reads what an account did: its orders and its fills.

@details One port for both histories rather than the two readers ADR D6
first named (amended 2026-09-30): they share the signed session, the symbol
requirement and the exchange's lookback window, and every consumer so far —
a desk's two history tabs, the Spot average entry price — wants both from the
same venue. It is still its own port, apart from `ITradingClient`, because
that one places orders and this one only reads (Interface Segregation).

**Complete or raise, never truncated.** Binance caps each request's time
span (Futures seven days, Spot twenty-four hours) and its row count. An
implementation splits the requested span into windows the exchange accepts,
and splits a window again when it comes back full, so a busy day is read in
full rather than cut at the row limit. A failure raises; it is never an
empty answer.

**At most thirty days back.** A `since` further back than
`MAX_HISTORY_LOOKBACK` is refused with `ValueError` before any request. Spot
reads a day per request at weight 20, so a year would cost about 7 300 weight
per symbol, over Binance's 6 000 a minute, and repeated 429s end in an IP ban
(the PR #297 review, finding 2). Thirty days is 600 weight per Spot symbol and
endpoint, covers ADR O5's seven-day tabs, and gives the average entry price a
month of fills to explain a holding; Futures keeps order history for 90 days,
so the ceiling never asks for what the exchange has dropped.

Plausible extensions, each one method or one implementation behind this
port: a COIN-M reader; funding and income history (`/fapi/v1/income`);
Futures position history once Binance exposes one; a caching decorator for
repeated page requests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)

#: The furthest back any history read may start (see the module docstring).
MAX_HISTORY_LOOKBACK = timedelta(days=30)


class IAccountHistoryReader(ABC):
    """One venue's order and trade history, read from the exchange."""

    @abstractmethod
    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        """@brief Every order on `symbol` created from `since` until now,
        oldest first.
        @throws ValueError `since` is older than `MAX_HISTORY_LOOKBACK`.
        @throws AccountHistoryUnavailableError The exchange did not answer."""

    @abstractmethod
    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        """@brief Every fill on `symbol` from `since` until now, oldest
        first. Raises as `order_history` does."""

    @abstractmethod
    def active_symbols(self) -> tuple[str, ...]:
        """@brief The pairs the account holds or has an open order on, the
        pairs a history of "every symbol" covers. Sorted.
        @throws AccountHistoryUnavailableError The exchange did not answer."""
