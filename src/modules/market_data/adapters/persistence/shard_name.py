"""Where a (market, symbol) pair's candles live on disk: the shard's name (`EPIC-027A`).

@details Split from `database_manager.py` by `EPIC-047H`: the bridge, a second process that starts fast on the
VPS, opens the host's shards read-only and must name them exactly as the host does, without importing
SQLAlchemy (`readonly_candle_shards.py`). One definition, two readers (P3).
"""

from __future__ import annotations

import re

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType

#: Binance symbols are uppercase alphanumerics only (`BTCUSDT`). Validated
#: here, not left to `SqliteShardManager`'s own `[A-Za-z0-9_-]+` pattern: that
#: pattern alone would accept an *empty* symbol once compounded with a market
#: prefix (`"spot_" + ""` is itself a valid shard name), silently laundering
#: exactly the input `test_security.py` exists to reject.
_VALID_SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9]+$")


def shard_name(market: MarketType, symbol: str) -> str:
    """@brief The on-disk shard name for one (market, symbol) pair.

    @details `EPIC-027A` — a market-qualified compound name (`spot_BTCUSDT`)
    rather than one subdirectory per market. `SqliteShardManager.directory`
    also doubles as its `IN_MEMORY` sentinel (`":memory:"`, matched by exact
    string equality); joining a per-market subdirectory onto it would silently
    stop matching that sentinel and start treating `":memory:/spot"` as a real
    filesystem path. Naming the shard itself keeps `directory` untouched (real
    path or `IN_MEMORY`, exactly as configured) so both backends stay correct,
    and it stays a one-`SqliteShardManager` design — see the class docstring.
    `MarketType` values are lowercase-with-underscores and Binance symbols are
    uppercase alphanumerics, so the two halves never collide, and
    `parse_shard_name` recovers them unambiguously.
    @raise ValueError if `symbol` is empty or is not itself a safe shard-name
    component (see `_VALID_SYMBOL_PATTERN`).
    """
    if not _VALID_SYMBOL_PATTERN.match(symbol):
        raise ValueError(f"Invalid symbol: {symbol!r}")
    return f"{market.value}_{symbol}"
