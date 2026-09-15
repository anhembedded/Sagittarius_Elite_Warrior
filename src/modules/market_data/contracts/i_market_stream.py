"""Port: *stream live candles for these symbols* (HLD §3.4, SDD-06b).

**Why this port exists.** Two screens open and close the live kline websocket
— the trading chart and the Dev Board — and both do it by building
`StartLiveStreamCommand` / `StopLiveStreamCommand` and dispatching them, so
both import `modules/market_data/application/`. That is the boundary rule's
one prohibition: a consumer may import a module's `contracts/` and nothing
else.

**What it fixes beyond the boundary.** The dispatcher's result is untyped, so
both call sites read it by probing:

    response = self._dispatcher.dispatch(StartLiveStreamCommand, cmd)
    if response and getattr(response, "success", True):
        ...
    message = getattr(response, "message", "Unknown error")

`getattr` with a default *on a boundary contract* is the shape
`architecture-rule.md` §2.1 forbids, and the default is the dangerous half:
`getattr(response, "success", True)` reports success for any object that has
no such field — including `None` — so a stream that never opened would tell
the user it is streaming. `StreamOutcome` below is a named type with both
fields, and there is nothing left to probe.

**Why this is not SDD-06b's declared shape, and what that costs.** The spec
declares `start(symbol, timeframe, owner_id) -> StreamHandle`,
`stop(handle)` and `stop_all(owner_id)` — one handle per stream, because one
owner may hold several. Today's mechanism cannot answer that: `BOT-126` made
`ILiveStreamService.subscribe(owner, symbols, interval)` *replace* an owner's
whole subscription set, reference-counted per `(symbol, interval)`, and a
per-stream handle would mean changing that service's semantics and the two
commands with it. ADR D12 says a port pull request changes no business
behaviour, so this port publishes what the module does today: a set of
symbols per owner, started and released together.

The precedent is PR 0.5's, taken for the same reason: SDD-06b declares
`IMarketDataSync.sync(...) -> SyncHandle` and `cancel(handle)`, and what
shipped is `sync(request) -> None` with a caller-owned `CancellationCheck`,
recorded in that port's own docstring. The handle shape belongs where a
second consumer needs it — `strategy` in Phase 2, which wants one stream per
armed symbol — and `stop(owner_id)` below is deliberately today's
`stop_all(owner_id)` and today's `stop(handle)` at once, because with one
subscription set per owner they are the same sentence.

**`owner_id`, not `owner`.** `Docs/VOCABULARY/README.md` names this a *stream
owner*: a **namespace**, not an exclusive lease. Two owners may stream the
same symbol; releasing one never touches the other. The command field is
still `owner`; the published name is the vocabulary's.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame


@dataclass(frozen=True, slots=True)
class StreamOutcome:
    """What happened, in the two facts both callers already show the user.

    A named type rather than the dispatcher's untyped response: every field a
    caller reads is declared here, so a missing one is an `AttributeError` at
    the call site instead of a `getattr` default quietly reporting success.
    """

    #: Whether the subscription set is now what the caller asked for.
    success: bool
    #: Ready to show a user. The implementation writes it; a caller that
    #: wants its own wording still has `success` to branch on.
    message: str


class IMarketStream(ABC):
    """Open and release this context's live kline stream, per owner."""

    @abstractmethod
    def start(
        self, owner_id: str, symbols: Sequence[str], interval: TimeFrame
    ) -> StreamOutcome:
        """Make `symbols` at `interval` this owner's whole subscription set.

        **Replaces, never adds** (`BOT-126`): calling it again for the same
        owner is how a screen changes symbol or timeframe, and it is safe
        without releasing first. Another owner's subscriptions are untouched
        even for the same `(symbol, interval)` pair, which is what keeps two
        screens from fighting over one stream (`BUG-085`).

        Symbols are upper-cased, and an empty `symbols` is a `ValueError`
        rather than a quiet no-op: a screen that reached here with nothing
        selected has a bug of its own, and an empty subscription set is
        indistinguishable from a stream that stopped.
        """

    @abstractmethod
    def stop(self, owner_id: str) -> StreamOutcome:
        """Release everything this owner holds; never another owner's.

        `success=False` means there was nothing to release — an ordinary
        state, not an error: a screen may stop a stream it never started
        (the trading chart's `stop()` is unconditional by design, its caller
        decides), and the message says so.
        """
