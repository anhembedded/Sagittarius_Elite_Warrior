import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import Optional
from datetime import datetime, timezone
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from sagittarius_engine.interfaces.i_config import IConfig
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

    def __init__(self, config: IConfig) -> None:
        db_url = config.get("database.url")
        if not db_url:
            # Fallback to an in-memory SQLite DB or safe relative path
            db_path = os.path.join(os.getcwd(), "database", "trading.db")
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
        @brief Upserts a batch of klines using SQLite's native ON CONFLICT DO UPDATE for high performance.
               Chunks the inserts to prevent database locks on massive syncs.
        """
        if not klines:
            return

        from sqlalchemy.dialects.sqlite import insert

        try:
            with self.Session() as session:
                # Prepare the SQLite UPSERT statement
                stmt = insert(KlineModel)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['symbol', 'interval', 'open_time'],
                    set_={
                        "open_price": stmt.excluded.open_price,
                        "high_price": stmt.excluded.high_price,
                        "low_price": stmt.excluded.low_price,
                        "close_price": stmt.excluded.close_price,
                        "volume": stmt.excluded.volume,
                        "close_time": stmt.excluded.close_time,
                        "quote_asset_volume": stmt.excluded.quote_asset_volume,
                        "number_of_trades": stmt.excluded.number_of_trades,
                        "taker_buy_base_asset_volume": stmt.excluded.taker_buy_base_asset_volume,
                        "taker_buy_quote_asset_volume": stmt.excluded.taker_buy_quote_asset_volume,
                    }
                )

                # Execute in chunks to avoid locking the DB for too long
                chunk_size = 5000
                for i in range(0, len(klines), chunk_size):
                    chunk = klines[i : i + chunk_size]
                    params = [
                        {
                            "symbol": k.symbol,
                            "interval": k.interval,
                            "open_time": k.open_time,
                            "open_price": k.open_price,
                            "high_price": k.high_price,
                            "low_price": k.low_price,
                            "close_price": k.close_price,
                            "volume": k.volume,
                            "close_time": k.close_time,
                            "quote_asset_volume": k.quote_asset_volume,
                            "number_of_trades": k.number_of_trades,
                            "taker_buy_base_asset_volume": k.taker_buy_base_asset_volume,
                            "taker_buy_quote_asset_volume": k.taker_buy_quote_asset_volume,
                        }
                        for k in chunk
                    ]
                    session.execute(stmt, params)
                    session.commit()
                    
                logger.debug(f"Saved {len(klines)} klines to database in chunks of {chunk_size}.")
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
        limit: Optional[int] = None,
        order_by_desc: bool = False,
    ) -> list[MarketData]:
        with self.Session() as session:
            query = session.query(KlineModel).filter_by(
                symbol=symbol, interval=interval.value
            )

            if start_time:
                query = query.filter(KlineModel.open_time >= start_time)
            if end_time:
                query = query.filter(KlineModel.open_time <= end_time)

            if order_by_desc:
                query = query.order_by(KlineModel.open_time.desc())
            else:
                query = query.order_by(KlineModel.open_time.asc())
                
            if limit is not None:
                query = query.limit(limit)

            rows = query.all()

            # If the caller didn't explicitly ask for desc, but we used limit, 
            # we should reverse it ONLY if we manually applied desc under the hood 
            # to get the latest, which we don't do anymore unless order_by_desc is True.
            # Wait, if order_by_desc is False, and limit=1000, we get the *oldest* 1000 candles.
            # If order_by_desc is True, we get the *newest* 1000 candles in descending order.
            # This makes the behavior predictable.

            results = []
            for row in rows:
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

    def get_database_status(self, symbol: str, interval: TimeFrame) -> dict:
        """
        @brief Retrieves status and gap count using SQLite Window Functions.
        """
        expected_seconds = interval.to_seconds()
        
        # We use a CTE or subquery with LAG to compute the previous candle time.
        # Then we aggregate the results in the outer query.
        # This executes entirely inside the SQLite engine, preventing OOM.
        query = sa.text(f"""
            WITH ordered_klines AS (
                SELECT 
                    open_time,
                    LAG(open_time) OVER (ORDER BY open_time ASC) as prev_time
                FROM klines
                WHERE symbol = :symbol AND interval = :interval
            )
            SELECT
                MIN(open_time) as first_record,
                MAX(open_time) as last_record,
                COUNT(*) as total_candles,
                SUM(CASE 
                    WHEN prev_time IS NOT NULL AND 
                         (strftime('%s', open_time) - strftime('%s', prev_time)) > :expected_seconds 
                    THEN 1 ELSE 0 
                END) as gaps
            FROM ordered_klines
        """)
        
        with self.Session() as session:
            result = session.execute(
                query, 
                {"symbol": symbol, "interval": interval.value, "expected_seconds": expected_seconds}
            ).fetchone()
            
            if not result or result[2] == 0:
                return {
                    "first_record": None,
                    "last_record": None,
                    "total_candles": 0,
                    "gaps": 0
                }
                
            return {
                "first_record": result[0].replace(tzinfo=timezone.utc) if isinstance(result[0], datetime) else (datetime.fromisoformat(result[0]).replace(tzinfo=timezone.utc) if result[0] else None),
                "last_record": result[1].replace(tzinfo=timezone.utc) if isinstance(result[1], datetime) else (datetime.fromisoformat(result[1]).replace(tzinfo=timezone.utc) if result[1] else None),
                "total_candles": result[2],
                "gaps": result[3] if result[3] is not None else 0
            }
