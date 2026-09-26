"""Port: *make sure this symbol's history is on disk* (HLD §3.2, §6.1).

**Why this port exists at all.** Four screens want the same thing — candles
for a symbol and timeframe, fetched if missing — and all four reach for it by
building `SyncMarketDataCommand` and dispatching it, which means every one of
them imports `modules/market_data/application/`. That is the boundary rule's
one prohibition: a consumer may import a module's `contracts/` and nothing
else. The command class is the module's *internals*; this port is the sentence
the module actually publishes.

`EPIC-025A` §1 item 8 calls it "making the skeleton walk with N = 2": a module
that nobody calls through a port has not proved the mechanism, whatever its
directory layout looks like.

**The request is a frozen dataclass, not the command.** `SyncMarketDataCommand`
is a `pydantic` model with a validator, a progress-correlation field and a
default for how far back to reach — the shape the handler wants. A consumer
should not have to know any of that, and `pydantic` has no business crossing a
published boundary. The DTO below carries exactly the six things the four
callers actually set, which is measured: `days_back_if_empty` is in the command
and **no caller has ever passed it**, so it is not here.

The DTO lives in this file rather than its own, following the port next door
(`i_market_data_repository.py` keeps `DatabaseStatusSnapshot` and
`RangeCoverageSnapshot` beside it): a request type and the one method that
takes it are the same abstraction level and change together, which is the only
thing `architecture-rule.md` §5 rule 3 accepts as a reason to share a file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

#: A caller-owned "should I stop?" check, polled between fetches. It is a
#: callable and not a token type because the caller owns cancellation
#: (`async-ui-action-rule.md`) and the module must not learn the Engine's
#: `CancellationToken` to read one bool.
type CancellationCheck = Callable[[], bool]


@dataclass(frozen=True, slots=True)
class MarketDataSyncRequest:
    """What to sync, and how the caller wants to be able to stop it."""

    #: One or more trading pairs. Normalised to upper case by the
    #: implementation, so a caller passing `"btcusdt"` is not an error — the
    #: same rule every other symbol entry point in this app follows.
    symbols: tuple[str, ...]
    interval: TimeFrame
    #: `EPIC-027A` — which market's shard(s) to sync. Required, not defaulted:
    #: every caller states it explicitly, so a request can never silently
    #: sync the wrong market's history.
    market: MarketType
    #: `None` means "the implementation decides where to start" — which is
    #: what three of the four callers want: continue from the newest candle
    #: already stored, or reach back a default window when there is none.
    start_time: datetime | None = None
    #: `None` means "up to now".
    end_time: datetime | None = None
    cancellation_requested: CancellationCheck | None = None
    #: Echoed on every progress event this request produces, so a caller
    #: watching the bus can tell its own sync apart from another screen's
    #: sync of the same symbol and timeframe (`BOT-122`). `None` lets the
    #: implementation generate one, which is right for a caller that never
    #: looks at the events.
    correlation_id: str | None = None


class IMarketDataSync(ABC):
    """Bring the local store up to date for one or more symbols."""

    @abstractmethod
    def sync(self, request: MarketDataSyncRequest) -> None:
        """Fetches whatever `request` names and is not stored yet.

        Returns nothing, and that is deliberate rather than unfinished: what
        the callers do next is read the store (`IMarketDataRepository`) or
        watch the progress events. Inventing a result object here would
        publish a promise no implementation makes — the handler this wraps
        has always returned `None`.

        Cancellation is cooperative: the implementation polls
        `request.cancellation_requested` between fetches and returns early,
        leaving whatever it has already stored in place.
        """
