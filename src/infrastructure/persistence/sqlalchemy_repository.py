import logging
from datetime import UTC, datetime

import sqlalchemy as sa
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.models import KlineModel

logger = logging.getLogger("App.Database")


class SQLAlchemyMarketDataRepository(IMarketDataRepository):
    """
    @brief SQLite/SQLAlchemy implementation of IMarketDataRepository.
    @details Ensures WAL mode is enabled for concurrent reads and writes.
             Delegates connection pooling to DatabaseManager.
    """

    _UPSERT_CHUNK_SIZE = 5000

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def save_klines(self, klines: list[MarketData]) -> None:
        """
        @brief Upserts a batch of klines using SQLite's native ON CONFLICT DO UPDATE for high performance.
               Chunks the inserts to prevent database locks on massive syncs.
        """
        if not klines:
            return

        try:
            symbol_groups = self._group_by_symbol(klines)
            stmt = self._build_upsert_stmt()

            for symbol, group_klines in symbol_groups.items():
                with self.db_manager.get_session(symbol) as session:
                    self._execute_chunked_upsert(session, stmt, group_klines)

                logger.debug(
                    f"Saved {len(group_klines)} klines for {symbol} to database "
                    f"in chunks of {self._UPSERT_CHUNK_SIZE}."
                )
        except Exception as e:
            logger.error(f"Failed to save klines to database: {e}")
            raise

    @staticmethod
    def _group_by_symbol(klines: list[MarketData]) -> dict[str, list[MarketData]]:
        symbol_groups: dict[str, list[MarketData]] = {}
        for k in klines:
            symbol_groups.setdefault(k.symbol, []).append(k)
        return symbol_groups

    @staticmethod
    def _build_upsert_stmt():
        """@brief Builds the SQLite-dialect ON CONFLICT DO UPDATE statement for KlineModel."""
        from sqlalchemy.dialects.sqlite import insert

        stmt = insert(KlineModel)
        return stmt.on_conflict_do_update(
            index_elements=["symbol", "interval", "open_time"],
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
            },
        )

    def _execute_chunked_upsert(self, session, stmt, klines: list[MarketData]) -> None:
        """@brief Executes the upsert in chunks of _UPSERT_CHUNK_SIZE using a core connection."""
        # Using Core connection directly bypasses ORM overhead for bulk execution.
        conn = session.connection()

        # We can map the chunk directly to dictionaries in one pass
        # avoiding unnecessary comprehension overhead
        for i in range(0, len(klines), self._UPSERT_CHUNK_SIZE):
            chunk = klines[i : i + self._UPSERT_CHUNK_SIZE]
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
            conn.execute(stmt, params)
        session.commit()

    def get_latest_kline_time(
        self, symbol: str, interval: TimeFrame
    ) -> datetime | None:
        with self.db_manager.get_session(symbol) as session:
            latest = (
                session.query(sa.func.max(KlineModel.open_time))
                .filter_by(symbol=symbol, interval=interval.value)
                .scalar()
            )
            if latest:
                return latest.replace(tzinfo=UTC)
            return None

    def get_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ) -> list[MarketData]:
        with self.db_manager.get_session(symbol) as session:
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

            return [self._to_market_data_entity(row) for row in query.all()]

    @staticmethod
    def _to_market_data_entity(row: KlineModel) -> MarketData:
        return MarketData(
            symbol=row.symbol,
            interval=row.interval,
            open_time=row.open_time.replace(tzinfo=UTC) if row.open_time else None,
            open_price=row.open_price,
            high_price=row.high_price,
            low_price=row.low_price,
            close_price=row.close_price,
            volume=row.volume,
            close_time=row.close_time.replace(tzinfo=UTC) if row.close_time else None,
            quote_asset_volume=row.quote_asset_volume,
            number_of_trades=row.number_of_trades,
            taker_buy_base_asset_volume=row.taker_buy_base_asset_volume,
            taker_buy_quote_asset_volume=row.taker_buy_quote_asset_volume,
        )

    @staticmethod
    def _build_status_query() -> sa.TextClause:
        # We use a CTE or subquery with LAG to compute the previous candle time.
        # Then we aggregate the results in the outer query.
        # This executes entirely inside the SQLite engine, preventing OOM.
        return sa.text("""
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
                         (unixepoch(open_time) - unixepoch(prev_time)) > :expected_seconds
                    THEN 1 ELSE 0 
                END) as gaps
            FROM ordered_klines
        """)

    def _map_status_result(self, result: tuple | None) -> DatabaseStatusSnapshot:
        if not result or result[2] == 0:
            return DatabaseStatusSnapshot(
                first_record=None,
                last_record=None,
                total_candles=0,
                gaps=0,
            )

        return DatabaseStatusSnapshot(
            first_record=self._parse_db_datetime(result[0]),
            last_record=self._parse_db_datetime(result[1]),
            total_candles=result[2],
            gaps=result[3] if result[3] is not None else 0,
        )

    def get_database_status(
        self, symbol: str, interval: TimeFrame
    ) -> DatabaseStatusSnapshot:
        """
        @brief Retrieves status and gap count using SQLite Window Functions.
        """
        expected_seconds = interval.to_seconds()
        query = self._build_status_query()

        with self.db_manager.get_session(symbol) as session:
            result = session.execute(
                query,
                {
                    "symbol": symbol,
                    "interval": interval.value,
                    "expected_seconds": expected_seconds,
                },
            ).fetchone()

            return self._map_status_result(result)

    @staticmethod
    def _parse_db_datetime(value) -> datetime | None:
        """
        @brief Normalizes a raw SQLite datetime result to a UTC-aware datetime.
        @details SQLite may return either a native datetime (typed column) or an ISO
        string (raw SQL aggregate result, as used by get_database_status's window
        function query) depending on the query path — this handles both.
        """
        if not value:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=UTC)
        return datetime.fromisoformat(value).replace(tzinfo=UTC)
