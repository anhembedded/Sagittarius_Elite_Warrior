"""`EPIC-028E` — reads what an account did: its orders and its fills.

@details One port for both histories rather than the two readers ADR D6
first named (amended 2026-09-30): they share the signed session, the symbol
requirement and the exchange's lookback window, and every consumer so far —
a desk's two history tabs, the Spot average entry price — wants both from the
same venue. It is still its own port, apart from `ITradingClient`, because
that one places orders and this one only reads (Interface Segregation).

**Complete or raise, never truncated at a span or row limit.** What the
exchange keeps, a read returns in full; what it never returns is stated
below under gaps. Binance caps each request's time
span (Futures seven days, Spot twenty-four hours) and its row count. An
implementation splits the requested span into windows the exchange accepts,
and splits a window again when it comes back full, so a busy day is read in
full rather than cut at the row limit. A failure raises; it is never an
empty answer.

**At most thirty days back.** A `since` further back than
`MAX_HISTORY_LOOKBACK` is refused with `ValueError` before any request. Spot
reads a day per request at weight 20, so a year would cost about 7 300 weight
per symbol, over Binance's 6 000 a minute, and repeated 429s end in an IP ban
(the PR #297 review, finding 2). Thirty days is 31 requests, 620 weight, per
Spot symbol and endpoint (both ends of the span are inclusive), covers ADR
O5's seven-day tabs, and gives the average entry price a month of fills to
explain a holding; Futures keeps order history for 90 days, so the ceiling
never asks for what the exchange has dropped. The check itself is
`history_lookback.require_within_lookback`, shared with the verified fake.

The bound is per symbol and endpoint. A history of every active symbol reads
each of them, and a page request reads the span again, so a caller that pages
through "every symbol" owns the aggregate cost (the PR #297 re-review,
finding 2; `EPIC-028J` carries it as an acceptance criterion). What one
every-symbol read may cost is the venue's to say, because the cost per pair
is: `every_symbol_scan_limit()` (`BUG-145`).

**Gaps are stated, not hidden** (`EPIC-028Q`). What the exchange does not
return at all (Futures' 3-day purge of unfilled cancelled orders, Spot's lack
of a traded-pairs index) is `known_gaps()`, which the history queries put on
each page.

Plausible extensions, each one method or one implementation behind this
port: a COIN-M reader; funding and income history (`/fapi/v1/income`);
Futures position history once Binance exposes one. The caching decorator for
repeated page requests is built (`CachedAccountHistoryReader`, `EPIC-028Q`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_gaps import (
    HistoryGaps,
)
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
    def active_symbols(self, since: datetime) -> tuple[str, ...]:
        """@brief The pairs a history of "every symbol" covers: those the
        account holds or has an open order on, plus every pair the venue can
        tell was traded from `since` on. Sorted. What a venue cannot tell is
        in `known_gaps().every_symbol`.
        @throws ValueError `since` is older than `MAX_HISTORY_LOOKBACK`.
        @throws AccountHistoryUnavailableError The exchange did not answer."""

    @abstractmethod
    def every_symbol_scan_limit(self) -> int | None:
        """@brief How many of `active_symbols` one every-symbol read may read
        within the exchange's request weight, or `None` for all of them
        (`BUG-145`). A positive count; no network read."""

    @abstractmethod
    def known_gaps(self) -> HistoryGaps:
        """@brief What this venue's history cannot show (`HistoryGaps`). No
        network read."""
