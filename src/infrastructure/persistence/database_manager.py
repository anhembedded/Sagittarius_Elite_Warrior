from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

import sqlalchemy as sa
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.models import Base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger("App.Database")

_VALID_SYMBOL_REGEX = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class DatabaseConfig:
    db_dir: str


class DatabaseManager:
    """
    @brief Singleton manager for handling SQLite Multi-Database connections (Sharding).
    @details Creates and caches database engines/sessions per symbol.
    """

    def __init__(self, config: DatabaseConfig) -> None:
        self.db_dir = config.db_dir

        # Don't create directory if memory DB is intended
        if self.db_dir != ":memory:":
            os.makedirs(self.db_dir, exist_ok=True)

        self._sessions: dict[str, sessionmaker] = {}  # Symbol -> SessionMaker
        logger.info(f"Database Manager initialized at directory: {self.db_dir}")

    def get_session(self, symbol: str):
        """
        @brief Retrieves or creates a SQLAlchemy session bound to a symbol-specific database.
        """
        if not _VALID_SYMBOL_REGEX.match(symbol):
            raise ValueError(f"Invalid symbol: {symbol}")

        if symbol in self._sessions:
            return self._sessions[symbol]()

        if self.db_dir == ":memory:":
            db_url = f"sqlite:///file:{symbol}?mode=memory&cache=shared&uri=true"
            db_path = f"memory:{symbol}"
        else:
            db_path = os.path.normpath(os.path.join(self.db_dir, f"{symbol}.db"))

            # Ensure safe path boundary by comparing commonpath with abspath
            base_dir = os.path.abspath(self.db_dir)
            abs_db_path = os.path.abspath(db_path)
            if os.path.commonpath([base_dir, abs_db_path]) != base_dir:
                raise PermissionError("Path traversal attempt detected")

            db_url = f"sqlite:///{db_path}"

        # connect_args to configure SQLite with WAL and a high timeout to prevent locking
        engine = sa.create_engine(
            db_url, connect_args={"check_same_thread": False, "timeout": 15}
        )

        # Enforce WAL mode on connect
        @sa.event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

        Base.metadata.create_all(engine)
        session_maker_instance = sessionmaker(bind=engine)
        self._sessions[symbol] = session_maker_instance

        logger.info(f"Created dedicated database for symbol {symbol} at {db_path}")
        return session_maker_instance()

    def list_shards(self) -> list[str]:
        """
        @brief Lists all symbol names that currently have existing database files on disk.
        """
        if self.db_dir == ":memory:":
            return sorted(self._sessions.keys())

        if not os.path.isdir(self.db_dir):
            return []

        symbols: list[str] = []
        for file_path in Path(self.db_dir).glob("*.db"):
            if file_path.is_file() and _VALID_SYMBOL_REGEX.match(file_path.stem):
                symbols.append(file_path.stem)
        return sorted(symbols)

    def remove_shard(self, symbol: str) -> bool:
        """
        @brief Closes connections and removes the SQLite database files for a specific symbol.
        @return True if files or active session were removed, False otherwise.
        """
        if not _VALID_SYMBOL_REGEX.match(symbol):
            raise ValueError(f"Invalid symbol: {symbol}")

        # Dispose session if cached
        session_factory = self._sessions.pop(symbol, None)
        if session_factory is not None:
            engine = session_factory.kw.get("bind")
            if engine is not None:
                engine.dispose()

        if self.db_dir == ":memory:":
            return session_factory is not None

        base_dir = os.path.abspath(self.db_dir)
        removed_any = False

        for suffix in [".db", ".db-wal", ".db-shm"]:
            candidate_path = os.path.normpath(
                os.path.join(self.db_dir, f"{symbol}{suffix}")
            )
            abs_path = os.path.abspath(candidate_path)
            if os.path.commonpath([base_dir, abs_path]) != base_dir:
                raise PermissionError("Path traversal attempt detected")

            if os.path.isfile(abs_path):
                try:
                    os.remove(abs_path)
                    removed_any = True
                except OSError as err:
                    logger.warning(f"Failed to remove {abs_path}: {err}")

        return removed_any or (session_factory is not None)

    def purge_all_shards(self) -> int:
        """
        @brief Disposes all engines and purges all SQLite shard files in the database directory.
        @return Total count of database shards purged.
        """
        self.dispose_all()
        shards = self.list_shards()
        count = len(shards)

        if self.db_dir == ":memory:":
            self._sessions.clear()
            return count

        base_dir = os.path.abspath(self.db_dir)
        for file_path in Path(self.db_dir).glob("*.db*"):
            if file_path.is_file():
                abs_path = os.path.abspath(str(file_path))
                if os.path.commonpath([base_dir, abs_path]) == base_dir:
                    try:
                        os.remove(abs_path)
                    except OSError as err:
                        logger.warning(f"Failed to delete {abs_path}: {err}")

        self._sessions.clear()
        logger.info(f"Purged {count} database shards from {self.db_dir}")
        return count

    def vacuum(self, symbol: str | None = None) -> None:
        """
        @brief Executes SQLite VACUUM and WAL checkpoint to compact database size.
        """
        targets = [symbol] if symbol is not None else self.list_shards()
        for sym in targets:
            if not _VALID_SYMBOL_REGEX.match(sym):
                continue
            try:
                with self.get_session(sym) as session:
                    session.execute(sa.text("PRAGMA wal_checkpoint(TRUNCATE)"))
                    session.execute(sa.text("VACUUM"))
                    logger.info(f"Vacuumed SQLite database for {sym}")
            except Exception as err:  # noqa: BLE001
                logger.warning(f"Vacuum failed for {sym}: {err}")

    def dispose_all(self) -> None:
        """Dispose every engine managed by this instance.

        Call this in test teardown (or application shutdown) to close all SQLite
        file handles and prevent ``ResourceWarning: unclosed database`` noise.
        """
        for session_factory in self._sessions.values():
            engine = session_factory.kw.get("bind")
            if engine is not None:
                engine.dispose()
        logger.debug("DatabaseManager: all engines disposed")
