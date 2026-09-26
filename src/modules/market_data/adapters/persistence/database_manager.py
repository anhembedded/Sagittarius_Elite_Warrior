from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.models import (
    Base,
)
from sagittarius_engine.extensions.persistence.sqlite_shard_manager import (
    IN_MEMORY,
    SqliteShardConfig,
    SqliteShardManager,
)
from sqlalchemy.orm import Session

#: SQLite's own WAL sidecar files — must move with their `.db` file or a
#: pending, not-yet-checkpointed write would be silently left behind under
#: the old name.
_SHARD_FILE_SUFFIXES = (".db", ".db-wal", ".db-shm")

logger = logging.getLogger("App.Database")


@dataclass(frozen=True)
class DatabaseConfig:
    db_dir: str


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


def parse_shard_name(name: str) -> tuple[MarketType, str] | None:
    """@brief Splits a shard name back into `(market, symbol)`.

    @return `None` when `name` carries no known market prefix — a legacy
    shard from before `EPIC-027A`, named after its bare symbol. Migrating
    those is `DatabaseManager.migrate_legacy_shards()`'s job, not this
    function's.
    """
    for market in MarketType:
        prefix = f"{market.value}_"
        if name.startswith(prefix):
            return market, name[len(prefix) :]
    return None


class DatabaseManager:
    """
    @brief Per-(market, symbol) SQLite sharding for this bot.

    @details Everything generic about "one SQLite file per shard" — lazy creation, WAL
    and `synchronous=NORMAL` pragmas, `check_same_thread`/timeout connect args, shard
    name validation, path-traversal containment, and the list/remove/purge/vacuum file
    management — lives in the engine's `SqliteShardManager` (engine `EPIC-004A`). This
    class is what remains once that is factored out: the bot's own vocabulary (a shard
    is a *symbol*, scoped to a *market*) and its own schema (`models.Base`).

    `EPIC-027A` — every shard name is market-qualified (`shard_name()`), so Spot and
    Futures candles of the same symbol live in different files and neither can
    overwrite the other. Every operation names its market explicitly; there is no
    default. Kept as one `SqliteShardManager` (not one per market — see `shard_name()`
    for why), so gap scan, vacuum and export/import, which already work per shard,
    need no change beyond the name they pass (ADR
    `DECISION_2026-09-26_spot_market_axis.md` §3).

    Public API is otherwise unchanged from the hand-rolled version this replaced —
    `get_session` still returns a raw SQLAlchemy `Session`, not the engine's
    `ISession`, because the repository layer uses `Session.connection()` for bulk
    upserts and reads more naturally against the full `Session` surface.
    """

    def __init__(self, config: DatabaseConfig) -> None:
        self.db_dir = config.db_dir
        self._shards = SqliteShardManager(
            SqliteShardConfig(directory=config.db_dir, metadata=Base.metadata)
        )
        logger.info(f"Database Manager initialized at directory: {self.db_dir}")

    def get_session(self, market: MarketType, symbol: str) -> Session:
        """
        @brief Retrieves a session bound to a (market, symbol)-specific database,
        creating it on first use.
        """
        name = shard_name(market, symbol)
        known = name in self._shards.names()
        session = self._shards.get_raw_session(name)
        if not known:
            logger.info(f"Created dedicated database for {market.value}/{symbol}")
        return session

    def list_shards(self, market: MarketType) -> list[str]:
        """
        @brief Lists all symbol names of one market that currently have existing
        database files on disk. Excludes shards of other markets and any
        not-yet-migrated legacy shard (`parse_shard_name` returns `None` for those).
        """
        prefix = f"{market.value}_"
        return sorted(
            name[len(prefix) :]
            for name in self._shards.names()
            if name.startswith(prefix)
        )

    def list_legacy_shard_names(self) -> list[str]:
        """
        @brief Shard names on disk that carry no market prefix at all.
        @details The set `migrate_legacy_shards()` acts on — every shard written
        before `EPIC-027A`, when a shard was named after its bare symbol.
        """
        return [name for name in self._shards.names() if parse_shard_name(name) is None]

    def migrate_legacy_shards(self) -> list[str]:
        """
        @brief One-time, idempotent migration of pre-`EPIC-027A` shards to Spot.
        @details ADR O3 (`DECISION_2026-09-26_spot_market_axis.md`, 2026-09-26):
        a shard written before this task carries no market column or prefix —
        but every candle in it was, in fact, downloaded from the mainnet public
        venue's `/api/v3/klines` (Spot) endpoint, the only one this app ever
        called before `EPIC-027A`. So it is tagged Spot, not guessed and not
        dropped. Renames the shard's files in place; never deletes data.

        Idempotent: a shard already migrated has no legacy name left for
        `list_legacy_shard_names()` to find, so a second call is a no-op.

        @details Must run before any shard in this `DatabaseManager` instance is
        opened. `SqliteShardManager` exposes no way to close one already-open
        engine without also deleting its file, so a legacy shard this process
        already opened cannot be renamed safely — call this immediately after
        construction, at boot, before anything resolves `IMarketDataRepository`.
        @return The bare symbol names migrated by this call (empty when there
        was nothing to do).
        """
        migrated: list[str] = []
        for legacy_symbol in self.list_legacy_shard_names():
            new_name = shard_name(MarketType.SPOT, legacy_symbol)
            self._rename_shard_files(legacy_symbol, new_name)
            migrated.append(legacy_symbol)
            logger.info(
                f"Migrated legacy shard {legacy_symbol!r} to Spot as {new_name!r} "
                "(ADR O3: pre-EPIC-027A shards were always Spot data)."
            )
        if migrated:
            logger.info(f"Migrated {len(migrated)} legacy shard(s) to Spot.")
        return migrated

    def _rename_shard_files(self, old_name: str, new_name: str) -> None:
        """@brief Renames one shard's `.db` file and its WAL sidecars, if any."""
        if self.db_dir == IN_MEMORY:
            return
        for suffix in _SHARD_FILE_SUFFIXES:
            old_path = os.path.join(self.db_dir, f"{old_name}{suffix}")
            if os.path.isfile(old_path):
                os.rename(old_path, os.path.join(self.db_dir, f"{new_name}{suffix}"))

    def has_shard(self, market: MarketType, symbol: str) -> bool:
        """
        @brief Checks whether a (market, symbol) already has a database file on disk,
        without creating one.
        @details BUG-078 — a pure status/read check must be able to answer "no data"
        for a symbol without triggering `get_session()`'s create-on-first-use side
        effect. Callers that only ever want to read must check this first and skip
        `get_session()` entirely when it's False.
        """
        return shard_name(market, symbol) in self._shards.names()

    def remove_shard(self, market: MarketType, symbol: str) -> bool:
        """
        @brief Closes connections and removes the SQLite database files for a specific
        (market, symbol).
        @return True if files or active session were removed, False otherwise.
        """
        return self._shards.remove_shard(shard_name(market, symbol))

    def purge_all_shards(self) -> int:
        """
        @brief Disposes all engines and purges all SQLite shard files in the database
        directory, across every market.
        @return Total count of database shards purged.
        """
        count = self._shards.purge_all()
        logger.info(f"Purged {count} database shards from {self.db_dir}")
        return count

    def vacuum(self, market: MarketType, symbol: str | None = None) -> None:
        """
        @brief Executes SQLite VACUUM and WAL checkpoint to compact database size for
        one market's shards.
        """
        targets = [symbol] if symbol is not None else self.list_shards(market)
        for sym in targets:
            name = shard_name(market, sym)
            try:
                self._shards.vacuum(name)
                logger.info(f"Vacuumed SQLite database for {market.value}/{sym}")
            except Exception as err:  # noqa: BLE001
                # Kept per-symbol so one unreadable shard cannot abort a maintenance
                # sweep over all the others.
                logger.warning(f"Vacuum failed for {market.value}/{sym}: {err}")

    def dispose_all(self) -> None:
        """Dispose every engine managed by this instance.

        Call this in test teardown (or application shutdown) to close all SQLite
        file handles and prevent ``ResourceWarning: unclosed database`` noise.
        """
        self._shards.dispose_all()
        logger.debug("DatabaseManager: all engines disposed")
