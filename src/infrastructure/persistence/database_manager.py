import os
import logging
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from dataclasses import dataclass
from Binace_Bot.src.infrastructure.persistence.models import Base

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
        if symbol in self._sessions:
            return self._sessions[symbol]()

        if self.db_dir == ":memory:":
            db_url = f"sqlite:///file:{symbol}?mode=memory&cache=shared"
            db_path = f"memory:{symbol}"
        else:
            db_path = os.path.join(self.db_dir, f"{symbol}.db")
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
