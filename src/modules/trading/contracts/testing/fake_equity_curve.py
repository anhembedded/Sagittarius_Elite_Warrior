"""`FakeEquityCurve` — `IEquityCurve`'s verified fake.

In-memory, no Qt and no network. A test says what the session's equity has
done and reads back how many times the curve was asked for.

@par Why `seed()` and not `record()`
The port has no write method, on purpose (`IEquityCurve`'s own docstring: the
only writer is the module's user-data stream). A consumer's test still has to
put samples *somewhere*, so the fake offers `seed()` — deliberately not named
`record`, so nothing in a consumer's test can be mistaken for the production
write path this port refuses to publish.
"""

from __future__ import annotations

from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.equity_sample import (
    EquitySample,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_equity_curve import (
    IEquityCurve,
)


class FakeEquityCurve(IEquityCurve):
    """The equity backlog a test says the session has."""

    def __init__(self, samples: Iterable[EquitySample] = ()) -> None:
        self._samples: tuple[EquitySample, ...] = tuple(samples)
        #: How many times the backlog was read. A screen asking once at
        #: construction is the design; asking per repaint is a defect a test
        #: should be able to see.
        self.reads = 0

    def seed(self, samples: Iterable[EquitySample]) -> None:
        """Replaces the whole backlog. Replaces rather than appends, matching
        the frozen-value shape of every other fake here: a test states the
        situation instead of building up to it."""
        self._samples = tuple(samples)

    def samples(self) -> tuple[EquitySample, ...]:
        self.reads += 1
        return self._samples
