"""`BUG-179` — counts the `MarketData` objects that came into being while a test ran.

@details BUG-025's memory proofs (`test_python_binance_client_unit.py` for the
Sync stream, `test_sqlalchemy_repository.py` for the repository stream) count
real `MarketData` instances on the GC heap — deterministic across machines/CI,
unlike sampling OS-level RSS (noisy and allocator-dependent; BUG-025's own
report says why an RSS-based test was rejected).

They used to compare every live `MarketData` with the count at the start.
Objects an earlier test of the same xdist worker still held, and released
during the measurement, made the difference negative (`-30`) and failed the
test with the worker's ordering, never with the stream; a negative offset
could just as well hide a leak of the same size. The watch holds what existed
at its start, so none of it can be released or have its id reused, and counts
only what was created afterwards.
"""

from __future__ import annotations

import gc

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData


class MarketDataWatch:
    """@brief `MarketData` created after construction and still alive."""

    def __init__(self) -> None:
        gc.collect()
        self._before = [obj for obj in gc.get_objects() if type(obj) is MarketData]
        self._before_ids = {id(obj) for obj in self._before}

    def new_live_count(self) -> int:
        gc.collect()
        return sum(
            1
            for obj in gc.get_objects()
            if type(obj) is MarketData and id(obj) not in self._before_ids
        )
