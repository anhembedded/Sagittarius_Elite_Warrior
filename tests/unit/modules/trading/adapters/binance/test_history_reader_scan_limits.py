"""`BUG-145` — each venue's reader states how many pairs an every-pair
history may read, from what one pair costs it.

@details The limit needs no network read, so the collaborators are bare
`Mock()`s that the call never touches; the reads themselves are covered in
`test_history_readers.py`.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.cached_history_reader import (
    CachedAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_history_reader import (
    FuturesHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_history_reader import (
    SPOT_EVERY_SYMBOL_SCAN_LIMIT,
    SpotHistoryReader,
)


def test_spot_caps_an_every_pair_read_by_its_weight_per_pair() -> None:
    """Eight one-day windows of weight 20 per pair and endpoint: five pairs
    over two tabs are 1 600 of Binance's 6 000 a minute."""
    reader = SpotHistoryReader(Mock(), Mock(), Mock())

    limit = reader.every_symbol_scan_limit()

    assert limit == SPOT_EVERY_SYMBOL_SCAN_LIMIT
    assert limit is not None
    assert limit * 8 * 20 * 2 <= 6000 // 3


def test_futures_reads_every_active_pair() -> None:
    """One seven-day window per pair, over pairs actually in use: no cap
    (the PR #344 review, finding 1)."""
    assert FuturesHistoryReader(Mock(), Mock()).every_symbol_scan_limit() is None


def test_the_cache_states_the_limit_of_the_reader_it_wraps() -> None:
    spot = SpotHistoryReader(Mock(), Mock(), Mock())

    assert (
        CachedAccountHistoryReader(spot).every_symbol_scan_limit()
        == SPOT_EVERY_SYMBOL_SCAN_LIMIT
    )
