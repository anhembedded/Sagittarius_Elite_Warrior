"""Port: *what has this session's equity done so far* (HLD §3.4).

**Why this port exists, measured.** Two screens draw the equity chart — the
Trading screen and the Dev Board — and both got there by resolving
`EquityCurveRecorder`, the application service `FuturesUserDataStream` writes
on every `ACCOUNT_UPDATE`. Two entries on the boundary allowlist, and both
files read exactly **one** thing off that service: the backlog. Nothing reads
it to write, nothing reads its size, nothing reads its ceiling.

So the port has one method and `architecture-rule.md` §7.2.1's condition is
met rather than anticipated: the seam is cut at the second consumer, and the
second consumer already exists.

@par Why the reader and the writer are not one port
`record()` is not here. The only writer is the module's own user-data stream,
which holds the concrete recorder — publishing a write method would let a
screen append a sample the venue never reported, which is exactly the kind of
convenient fiction `domain-truth-rule.md` exists to prevent. A port is the
sentence a *consumer* needs, not a copy of the class behind it.

@par Live updates are a separate mechanism, deliberately
A screen wants the backlog once, at construction, and then every new sample
as it arrives. This port answers the first half; the second is
`EquitySampledEvent` on the bus, normalised by one Feed
(`architecture-rule.md` §6.2). Folding a subscription into this port would
give the same fact two delivery paths that could disagree about ordering.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)


class IEquityCurve(ABC):
    """Read this session's equity samples."""

    @abstractmethod
    def samples(self) -> tuple[EquitySample, ...]:
        """Every sample recorded so far, oldest first, empty before the first.

        A tuple, so a caller cannot hand the next reader a list it has since
        edited — the same immutability `IAccountSnapshot.open_positions()`
        answers with, and the property this replaced had to defend by copying
        its `deque` on every read.

        Bounded: the implementation keeps the most recent samples and evicts
        the oldest, so a long-running session cannot grow this without limit.
        Not a rendering concern — a caller that wants fewer points thins them
        itself.
        """
