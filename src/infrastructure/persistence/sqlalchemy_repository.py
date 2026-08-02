import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import Optional
from datetime import datetime, timezone
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.application.interfaces.i_market_data_repository import (
    IMarketDataRepository,
)
import os
import logging

logger = logging.getLogger("App.Database")

Base = declarative_base()


class KlineModel(Base):
    __tablename__ = "klines"

    # Composite Primary Key to ensure we don't duplicate klines
    symbol = sa.Column(sa.String, primary_key=True)
    interval = sa.Column(sa.String, primary_key=True)
    open_time = sa.Column(sa.DateTime, primary_key=True)

    open_price = sa.Column(sa.Float, nullable=False)
    high_price = sa.Column(sa.Float, nullable=False)
    low_price = sa.Column(sa.Float, nullable=False)
    close_price = sa.Column(sa.Float, nullable=False)
    volume = sa.Column(sa.Float, nullable=False)
    close_time = sa.Column(sa.DateTime, nullable=False)
    quote_asset_volume = sa.Column(sa.Float, nullable=False)
    number_of_trades = sa.Column(sa.Integer, nullable=False)
    taker_buy_base_asset_volume = sa.Column(sa.Float, nullable=False)
    taker_buy_quote_asset_volume = sa.Column(sa.Float, nullable=False)


class SQLAlchemyMarketDataRepository(IMarketDataRepository):
    """
    @brief SQLite/SQLAlchemy implementation of IMarketDataRepository.
    @details Ensures WAL mode is enabled for concurrent reads and writes.
    """

    def __init__(self, db_url: Optional[str] = None) -> None:
        if db_url is None:
            # Use absolute path to avoid SQLAlchemy parsing issues
            db_path = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), "../../..", "database", "trading.db"
                )
            )
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
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
        self.Session = sessionmaker(bind=engine)
        logger.info(f"Database initialized at {db_url}")

    def save_klines(self, klines: list[MarketData]) -> None:
        """
        @brief Upserts a batch of klines. SQLite doesn't natively support ON CONFLICT easily in standard ORM bulk,
               so we use the modern SQLite 'INSERT OR REPLACE' equivalent or merge.
        """
        if not klines:
            return

        try:
            with self.Session() as session:
                for kline in klines:
                    model = KlineModel(
                        symbol=kline.symbol,
                        interval=kline.interval,
                        open_time=kline.open_time,
                        open_price=kline.open_price,
                        high_price=kline.high_price,
                        low_price=kline.low_price,
                        close_price=kline.close_price,
                        volume=kline.volume,
                        close_time=kline.close_time,
                        quote_asset_volume=kline.quote_asset_volume,
                        number_of_trades=kline.number_of_trades,
                        taker_buy_base_asset_volume=kline.taker_buy_base_asset_volume,
                        taker_buy_quote_asset_volume=kline.taker_buy_quote_asset_volume,
                    )
                    session.merge(model)
                session.commit()
                logger.debug(f"Saved {len(klines)} klines to database.")
        except Exception as e:
            logger.error(f"Failed to save klines to database: {e}")
            raise

    def get_latest_kline_time(
        self, symbol: str, interval: TimeFrame
    ) -> Optional[datetime]:
        with self.Session() as session:
            latest = (
                session.query(sa.func.max(KlineModel.open_time))
                .filter_by(symbol=symbol, interval=interval.value)
                .scalar()
            )
            if latest:
                return latest.replace(tzinfo=timezone.utc)
            return None

    def get_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[MarketData]:
        with self.Session() as session:
            query = session.query(KlineModel).filter_by(
                symbol=symbol, interval=interval.value
            )

            if start_time:
                query = query.filter(KlineModel.open_time >= start_time)
            if end_time:
                query = query.filter(KlineModel.open_time <= end_time)

            query = query.order_by(KlineModel.open_time.asc())

            results = []
            for row in query.all():
                results.append(
                    MarketData(
                        symbol=row.symbol,
                        interval=row.interval,
                        open_time=row.open_time.replace(tzinfo=timezone.utc)
                        if row.open_time
                        else None,
                        open_price=row.open_price,
                        high_price=row.high_price,
                        low_price=row.low_price,
                        close_price=row.close_price,
                        volume=row.volume,
                        close_time=row.close_time.replace(tzinfo=timezone.utc)
                        if row.close_time
                        else None,
                        quote_asset_volume=row.quote_asset_volume,
                        number_of_trades=row.number_of_trades,
                        taker_buy_base_asset_volume=row.taker_buy_base_asset_volume,
                        taker_buy_quote_asset_volume=row.taker_buy_quote_asset_volume,
                    )
                )
            return results
