"""Port: *read stored candles* (HLD §3.4, §6.1).

**Why this port exists.** Six call sites build `GetHistoricalKlinesQuery` and
dispatch it — two backtest coordinators, the trading chart, the Dev Board
stream controller, Data Management's kline inspector and the CLI's
`trade-once`. Every one of them therefore imports
`modules/market_data/application/`, which is the boundary rule's one
prohibition: a consumer may import a module's `contracts/` and nothing else.

**What it fixes beyond the boundary.** The handler's return type is
`list[MarketData] | dict[str, list[MarketData]]`, chosen by whether `symbol`
was a `str` or a `list`. A union decided by an argument's *runtime type* is the
shape `architecture-rule.md` §2.1 forbids, and the trading chart shows what it
costs: it asks for `symbol=[symbol]` — a list of one — to get a dict back, then
unwraps it through `getattr(response, "data", response)`, a `.get(symbol, [])`
and an `isinstance(results, dict)` guard. Four defensive steps to say *give me
this symbol's candles*. Two methods with one return type each remove all four.

**One symbol and many are separate questions.** Only the Dev Board genuinely
loads several symbols at once, and it wants them keyed by symbol; the other
five want one symbol's rows. `load()` and `load_many()` say which question is
being asked, instead of making the answer's shape depend on an argument.

**A tuple, not a list.** The rows are a snapshot of what is stored, and a
caller that appends to them is not communicating that to anyone
(`domain-truth-rule.md`'s "snapshot immutable"). `MarketData` is already
frozen; the container now matches it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

#: What every caller passes today when it does not care how far back the rows
#: reach — the handler's own default, kept so moving onto this port changes no
#: caller's behaviour (ADR D12: no change in business behaviour).
DEFAULT_KLINE_LIMIT = 1000


class IHistoricalKlines(ABC):
    """Read candles this context has already stored. Never fetches."""

    @abstractmethod
    def load(
        self,
        symbol: str,
        interval: TimeFrame,
        *,
        limit: int = DEFAULT_KLINE_LIMIT,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        newest_first: bool = False,
    ) -> tuple[MarketData, ...]:
        """One symbol's stored candles, empty when this shard has none.

        Empty rather than an error, and rather than `None`: "nothing stored
        yet" is the ordinary state of a symbol the user has not synced, which
        every caller already handles by showing an empty chart and saying so.
        Raising would make the normal case exceptional.

        `newest_first` selects *which* rows a `limit` keeps, not merely their
        order: with it set, a range holding more rows than `limit` keeps the
        **most recent** ones. Three callers pass it and then reverse the
        result, which is how they say "the newest N, chronologically" — worth
        naming as its own question one day, but not before `backtesting` owns
        its side of it in Phase 3.
        """

    @abstractmethod
    def load_many(
        self,
        symbols: Sequence[str],
        interval: TimeFrame,
        *,
        limit: int = DEFAULT_KLINE_LIMIT,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        newest_first: bool = False,
    ) -> Mapping[str, tuple[MarketData, ...]]:
        """Several symbols at once, keyed by symbol.

        Every symbol asked for appears in the result, mapped to an empty tuple
        when nothing is stored for it — so a caller can iterate its own
        request without checking whether each key exists, and a symbol that
        silently vanished from the answer cannot be mistaken for one with no
        data.

        Separate from `load()` because the implementation is allowed to fetch
        the symbols concurrently, which is the only reason a caller would ask
        this way rather than looping.
        """
