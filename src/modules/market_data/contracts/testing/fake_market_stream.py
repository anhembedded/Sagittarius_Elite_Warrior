"""The verified fake for `IMarketStream` (HLD §10.3).

**Who needs it.** The trading chart and the Dev Board open and release the
live stream, and `IMarketStream` is a *foreign* port to both, so
`Mock(spec=IMarketStream)` is not an option — `test_no_foreign_port_is_mocked.py`
fails on it, because a mock agrees with whatever the test asserts and cannot
notice the day the port's real behaviour changes.

**What it does and does not do.** It keeps the subscription *bookkeeping* —
which owner holds which symbols at which interval, replaced on every start
and dropped on stop — and opens no socket. That is the division a consumer's
test needs: the screen's promise is "this owner now streams these symbols",
and whether bytes arrive is the websocket adapter's contract, not this one's.

A test that wants a tick to arrive publishes `MarketTickEvent` on the bus,
exactly as the real adapter does; nothing about this fake pretends otherwise.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
    StreamOutcome,
)

#: What the real handlers answer, kept here so a consumer's test reads the
#: same words a user would see. The real messages live in
#: `start_live_stream/handler.py` and `stop_live_stream/handler.py`; the
#: contract suite asserts on `success`, never on the wording, so these being
#: prose rather than constants shared with the handler is deliberate — a
#: message is not part of the promise.
_STARTED = "Live stream started successfully."
_STOPPED = "Live stream stopped successfully."
_NOTHING_TO_STOP = "Failed to stop live stream. It might not be running."


@dataclass(frozen=True, slots=True)
class Subscription:
    """One owner's current subscription set, as the caller asked for it."""

    owner_id: str
    symbols: tuple[str, ...]
    interval: TimeFrame


class FakeMarketStream(IMarketStream):
    """Subscription bookkeeping a test controls, and no socket."""

    def __init__(self) -> None:
        self._held: dict[str, Subscription] = {}
        #: Every `start`/`stop` call, in order. A consumer's test often needs
        #: "the screen re-subscribed after the timeframe changed" or "it
        #: released on shutdown" — facts about the screen, not the socket.
        self.calls: list[tuple[str, str]] = []

    # -- IMarketStream -------------------------------------------------------

    def start(
        self, owner_id: str, symbols: Sequence[str], interval: TimeFrame
    ) -> StreamOutcome:
        requested = tuple(symbol.upper() for symbol in symbols)
        if not requested:
            # Same refusal, same place: `StartLiveStreamCommand`'s validator
            # raises on an empty list, so a screen that reached here with
            # nothing selected fails in a test rather than in production.
            raise ValueError("Symbols list cannot be empty")
        if not owner_id.strip():
            raise ValueError("owner cannot be empty")

        self.calls.append(("start", owner_id))
        # Replaces, never adds (`BOT-126`) — the whole reason two screens can
        # stream at once without fighting.
        self._held[owner_id] = Subscription(
            owner_id=owner_id, symbols=requested, interval=interval
        )
        return StreamOutcome(success=True, message=_STARTED)

    def stop(self, owner_id: str) -> StreamOutcome:
        if not owner_id.strip():
            raise ValueError("owner cannot be empty")

        self.calls.append(("stop", owner_id))
        if self._held.pop(owner_id, None) is None:
            return StreamOutcome(success=False, message=_NOTHING_TO_STOP)
        return StreamOutcome(success=True, message=_STOPPED)

    # -- what a consumer's test usually wants to know ------------------------

    def held_by(self, owner_id: str) -> Subscription | None:
        """This owner's current subscription set, or `None` if it holds none."""
        return self._held.get(owner_id)

    def is_streaming(self, symbol: str, interval: TimeFrame | None = None) -> bool:
        """Whether **any** owner currently streams this symbol.

        Case-insensitive on the symbol, because the port upper-cases on the
        way in and a test asking in the case the user typed is asking about
        the same symbol — not a near miss that silently answers no.
        """
        wanted = symbol.upper()
        return any(
            wanted in subscription.symbols
            and (interval is None or subscription.interval == interval)
            for subscription in self._held.values()
        )
