from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PruneEmptyShardsCommand:
    """
    @brief Command to remove every storage shard that holds zero klines.
    @details BUG-077 — a shard is created as a side effect of a read (fixed
    separately), so the vault can accumulate empty `.db` files for symbols that
    were only ever checked, never actually synced. This command is the explicit,
    opt-in remediation: it never touches a shard that has at least one kline in
    any interval (see `IMarketDataRepository.has_any_klines`).
    """

    cancellation_requested: Callable[[], bool] | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class PruneEmptyShardsResult:
    """
    @brief Typed outcome of executing a PruneEmptyShardsCommand.
    """

    removed_symbols: list[str]
    scanned_count: int
