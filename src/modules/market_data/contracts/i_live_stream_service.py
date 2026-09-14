"""
@brief `ILiveStreamService` — the port for subscribing to/releasing live
market-data streams, scoped per caller (`BOT-126`).

@details Declared in the Application layer, implemented in Infrastructure.
`ABC` (not `Protocol`), same reasoning as `i_cqrs.py`: a structural
`Protocol` lets an incomplete implementation construct successfully and
fail later somewhere else, while an `ABC` refuses construction and names
the missing method.

`BOT-126` replaced the original `start_stream(symbols, interval)`/
`stop_stream()` shape — a single process-wide stream with no caller
identity, where whichever screen called `start_stream()` last decided
which symbol/interval reached every screen, and `stop_stream()` (no
arguments) stopped it outright for everyone. `subscribe`/`release_owner`
below are reference-counted per `(symbol, interval)`, keyed by an opaque
`owner` string each caller picks for itself (one screen = one stable
owner id, since this app never runs two instances of the same screen at
once) — two owners can hold the same or different `(symbol, interval)`
pairs at once, and releasing one owner's subscriptions never touches
another owner's.
"""

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame


class ILiveStreamService(ABC):
    """
    @brief Port interface for subscribing to/releasing the live market data
    stream, scoped per caller (`owner`).
    """

    @abstractmethod
    def subscribe(self, owner: str, symbols: list[str], interval: TimeFrame) -> bool:
        """
        @brief Replaces `owner`'s entire set of active subscriptions with
        `symbols`/`interval`. Safe to call again for the same `owner`
        without releasing first — it replaces rather than adds.
        @return True once the subscription set was applied.
        """
        ...

    @abstractmethod
    def release_owner(self, owner: str) -> bool:
        """
        @brief Drops every subscription held by `owner`, if any. Never
        affects another owner's subscriptions, even for the same
        `(symbol, interval)` pair.
        @return True if `owner` had an active subscription that was
        removed, False if there was nothing to do.
        """
        ...

    @abstractmethod
    def stop_all(self) -> bool:
        """
        @brief Tears down every subscription for every owner, regardless of
        who holds them. For process-wide teardown (Engine shutdown) only —
        screens must use `release_owner` instead.
        @return True if anything was actually running, False if already idle.
        """
        ...
