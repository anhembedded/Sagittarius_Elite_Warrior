from __future__ import annotations

import logging
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.infrastructure.persistence.models import Base
from sagittarius_engine.extensions.persistence.sqlite_shard_manager import (
    SqliteShardConfig,
    SqliteShardManager,
)
from sqlalchemy.orm import Session

logger = logging.getLogger("App.Database")


@dataclass(frozen=True)
class DatabaseConfig:
    db_dir: str


class DatabaseManager:
    """
    @brief Per-symbol SQLite sharding for this bot.

    @details Everything generic about "one SQLite file per shard" — lazy creation, WAL
    and `synchronous=NORMAL` pragmas, `check_same_thread`/timeout connect args, shard
    name validation, path-traversal containment, and the list/remove/purge/vacuum file
    management — now lives in the engine's `SqliteShardManager` (engine `EPIC-004A`).
    This class is what remains once that is factored out: the bot's own vocabulary
    (a shard is a *symbol*) and its own schema (`models.Base`).

    Public API is unchanged from the hand-rolled version this replaced — `get_session`
    still returns a raw SQLAlchemy `Session`, not the engine's `ISession`, because the
    repository layer uses `Session.connection()` for bulk upserts and reads more
    naturally against the full `Session` surface.
    """

    def __init__(self, config: DatabaseConfig) -> None:
        self.db_dir = config.db_dir
        self._shards = SqliteShardManager(
            SqliteShardConfig(directory=config.db_dir, metadata=Base.metadata)
        )
        logger.info(f"Database Manager initialized at directory: {self.db_dir}")

    def get_session(self, symbol: str) -> Session:
        """
        @brief Retrieves a session bound to a symbol-specific database, creating it
        on first use.
        """
        known = symbol in self._shards.names()
        session = self._shards.get_raw_session(symbol)
        if not known:
            logger.info(f"Created dedicated database for symbol {symbol}")
        return session

    def list_shards(self) -> list[str]:
        """
        @brief Lists all symbol names that currently have existing database files on disk.
        """
        return self._shards.list_shards()

    def has_shard(self, symbol: str) -> bool:
        """
        @brief Checks whether a symbol already has a database file on disk, without
        creating one.
        @details BUG-077 — a pure status/read check must be able to answer "no data"
        for a symbol without triggering `get_session()`'s create-on-first-use side
        effect. Callers that only ever want to read must check this first and skip
        `get_session()` entirely when it's False.
        """
        return symbol in self._shards.names()

    def remove_shard(self, symbol: str) -> bool:
        """
        @brief Closes connections and removes the SQLite database files for a specific symbol.
        @return True if files or active session were removed, False otherwise.
        """
        return self._shards.remove_shard(symbol)

    def purge_all_shards(self) -> int:
        """
        @brief Disposes all engines and purges all SQLite shard files in the database directory.
        @return Total count of database shards purged.
        """
        count = self._shards.purge_all()
        logger.info(f"Purged {count} database shards from {self.db_dir}")
        return count

    def vacuum(self, symbol: str | None = None) -> None:
        """
        @brief Executes SQLite VACUUM and WAL checkpoint to compact database size.
        """
        targets = [symbol] if symbol is not None else self.list_shards()
        for sym in targets:
            try:
                self._shards.vacuum(sym)
                logger.info(f"Vacuumed SQLite database for {sym}")
            except Exception as err:  # noqa: BLE001
                # Kept per-symbol so one unreadable shard cannot abort a maintenance
                # sweep over all the others.
                logger.warning(f"Vacuum failed for {sym}: {err}")

    def dispose_all(self) -> None:
        """Dispose every engine managed by this instance.

        Call this in test teardown (or application shutdown) to close all SQLite
        file handles and prevent ``ResourceWarning: unclosed database`` noise.
        """
        self._shards.dispose_all()
        logger.debug("DatabaseManager: all engines disposed")
