import logging
import os
import re
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from Sagittarius_Elite_Warrior.src.infrastructure.persistence.models import Base

logger = logging.getLogger("App.Database")


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

        self._sessions = {}  # Symbol -> SessionMaker
        logger.info(f"Database Manager initialized at directory: {self.db_dir}")

    def get_session(self, symbol: str):
        """
        @brief Retrieves or creates a SQLAlchemy session bound to a symbol-specific database.
        """
        if not re.match(r"^[A-Za-z0-9_-]+$", symbol):
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
        SessionMaker = sessionmaker(bind=engine)
        self._sessions[symbol] = SessionMaker

        logger.info(f"Created dedicated database for symbol {symbol} at {db_path}")
        return SessionMaker()

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
