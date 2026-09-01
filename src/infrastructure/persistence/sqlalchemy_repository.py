import logging
from collections.abc import Iterator
from datetime import UTC, datetime

import sqlalchemy as sa
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
    IMarketDataRepository,
    RangeCoverageSnapshot,
)
from Sagittarius_Elite_Warrior.src.application.services.backtest_range_coverage import (
    as_utc,
    ceil_open_time,
    floor_open_time,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.models.data_gap import DataGap
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.kline_row_mapper import (
    build_gaps_query,
    build_range_coverage_query,
    build_status_query,
    build_upsert_stmt,
    map_status_result,
    parse_db_datetime,
    to_market_data_entity,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.models import KlineModel

logger = logging.getLogger("App.Database")

#: BUG-025 — `stream_klines()`'s server-side fetch batch size: how many ORM
#: rows SQLAlchemy materializes per round trip, independent of how many rows
#: the caller's own `limit` ultimately asks for. Tunable purely for this
#: side's DB read performance — **not** the same knob as `client.py`'s
#: `_KLINE_STREAM_CHUNK_SIZE` (Binance REST page size, an external API
#: limit), which happens to share this value and this name but answers a
#: different question (`EPIC-018` ADR D6: two independent tunables, kept
#: separate on purpose — changing Binance's page size has no reason to
#: change SQLAlchemy's batch size, or vice versa).
_KLINE_STREAM_CHUNK_SIZE = 1000


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
            stmt = build_upsert_stmt()

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
        if not self.db_manager.has_shard(symbol):
            return None
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
        if not self.db_manager.has_shard(symbol):
            return []
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

            return [to_market_data_entity(row) for row in query.all()]

    def count_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> int:
        if not self.db_manager.has_shard(symbol):
            return 0
        with self.db_manager.get_session(symbol) as session:
            query = session.query(KlineModel).filter_by(
                symbol=symbol, interval=interval.value
            )

            if start_time:
                query = query.filter(KlineModel.open_time >= start_time)
            if end_time:
                query = query.filter(KlineModel.open_time <= end_time)
            if limit is not None:
                query = query.limit(limit)

            return query.count()

    def stream_klines(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        offset: int | None = None,
        limit: int | None = None,
        order_by_desc: bool = False,
    ) -> Iterator[MarketData]:
        if not self.db_manager.has_shard(symbol):
            return
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

            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)

            for row in query.yield_per(_KLINE_STREAM_CHUNK_SIZE):
                yield to_market_data_entity(row)

    def get_database_status(
        self, symbol: str, interval: TimeFrame
    ) -> DatabaseStatusSnapshot:
        """
        @brief Retrieves status and gap count using SQLite Window Functions.
        """
        if not self.db_manager.has_shard(symbol):
            return DatabaseStatusSnapshot(
                first_record=None, last_record=None, total_candles=0, gaps=0
            )

        query = build_status_query()
        with self.db_manager.get_session(symbol) as session:
            result = session.execute(
                query,
                {
                    "symbol": symbol,
                    "interval": interval.value,
                    "expected_seconds": interval.to_seconds(),
                },
            ).fetchone()

            return map_status_result(result)

    def get_database_status_for_intervals(
        self, symbol: str, intervals: list[TimeFrame]
    ) -> dict[str, DatabaseStatusSnapshot]:
        """
        @brief Status for every interval of one symbol, opened over a single session.
        @details BUG-077 — `klines` is a single table per shard keyed on
        `(symbol, interval, open_time)`; all intervals of one symbol already live in
        the same SQLite file. Querying interval-by-interval on a fresh
        `get_session()` each time (the shape `ScanAllDatabasesQueryHandler` used to
        use) opens one SQLite connection per (symbol, interval) pair for no reason —
        connection setup, not the query itself, dominates the cost on a large scan.
        Opening the shard once and looping intervals inside it cuts connection count
        6x for the default interval set.
        """
        empty = DatabaseStatusSnapshot(
            first_record=None, last_record=None, total_candles=0, gaps=0
        )
        if not self.db_manager.has_shard(symbol):
            return {interval.value: empty for interval in intervals}

        query = build_status_query()
        results: dict[str, DatabaseStatusSnapshot] = {}
        with self.db_manager.get_session(symbol) as session:
            for interval in intervals:
                result = session.execute(
                    query,
                    {
                        "symbol": symbol,
                        "interval": interval.value,
                        "expected_seconds": interval.to_seconds(),
                    },
                ).fetchone()
                results[interval.value] = map_status_result(result)
        return results

    def get_range_coverage(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: datetime | None,
        end_time: datetime,
        now: datetime,
    ) -> RangeCoverageSnapshot:
        """Run the range probe entirely in SQLite and return six scalars."""
        if not self.db_manager.has_shard(symbol):
            return RangeCoverageSnapshot(None, None, 0, 0, None, 0)

        interval_seconds = interval.to_seconds()
        closed_end = floor_open_time(
            min(as_utc(end_time), as_utc(now)), interval_seconds
        )
        aligned_start = (
            ceil_open_time(as_utc(start_time), interval_seconds)
            if start_time is not None
            else None
        )
        query = build_range_coverage_query()
        with self.db_manager.get_session(symbol) as session:
            result = session.execute(
                query,
                {
                    "symbol": symbol,
                    "interval": interval.value,
                    "start_time": aligned_start,
                    "closed_end": closed_end,
                    "now": now,
                    "expected_seconds": interval_seconds,
                },
            ).fetchone()
        if not result or result[2] == 0:
            return RangeCoverageSnapshot(None, None, 0, 0, None, 0)
        return RangeCoverageSnapshot(
            first_record=parse_db_datetime(result[0]),
            last_record=parse_db_datetime(result[1]),
            total_candles=int(result[2]),
            distinct_candles=int(result[3]),
            first_gap_after=parse_db_datetime(result[4]),
            unclosed_candles=int(result[5] or 0),
        )

    def clear_klines(self, symbol: str, interval: TimeFrame | None = None) -> int:
        """
        @brief Deletes klines for a given symbol and optional interval.
        @details If interval is None, removes the entire shard database file to reclaim disk space.
        If interval is specified, deletes matching rows in KlineModel and commits.
        """
        if interval is None:
            count = 0
            try:
                with self.db_manager.get_session(symbol) as session:
                    count = session.query(KlineModel).filter_by(symbol=symbol).count()
            except Exception as err:  # noqa: BLE001
                logger.debug(f"Could not count klines before shard removal: {err}")
            self.db_manager.remove_shard(symbol)
            return count

        with self.db_manager.get_session(symbol) as session:
            stmt = sa.delete(KlineModel).where(
                KlineModel.symbol == symbol,
                KlineModel.interval == interval.value,
            )
            result = session.execute(stmt)
            deleted_count = result.rowcount
            session.commit()
            return int(deleted_count)

    def purge_all(self) -> int:
        """
        @brief Purges all market data databases / shards.
        @return Total count of shards purged.
        """
        return self.db_manager.purge_all_shards()

    def list_available_shards(self) -> list[str]:
        """
        @brief Lists all symbol names that have existing storage shards on disk.
        """
        return self.db_manager.list_shards()

    def vacuum(self, symbol: str | None = None) -> None:
        """
        @brief Compacts SQLite storage files by running VACUUM.
        """
        self.db_manager.vacuum(symbol)

    def get_gaps(self, symbol: str, interval: TimeFrame) -> list[DataGap]:
        """
        @brief Retrieves all gaps in historical market data for a symbol/interval.
        """
        if not self.db_manager.has_shard(symbol):
            return []

        expected_seconds = interval.to_seconds()
        query = build_gaps_query()
        with self.db_manager.get_session(symbol) as session:
            rows = session.execute(
                query,
                {
                    "symbol": symbol,
                    "interval": interval.value,
                    "expected_seconds": expected_seconds,
                },
            ).fetchall()

            gaps: list[DataGap] = []
            for row in rows:
                start_dt = parse_db_datetime(row[0])
                end_dt = parse_db_datetime(row[1])
                if start_dt is not None and end_dt is not None:
                    gaps.append(
                        DataGap(
                            symbol=symbol,
                            interval=interval,
                            start_time=start_dt,
                            end_time=end_dt,
                            missing_candles=max(1, int(row[2] or 1)),
                        )
                    )
            return gaps

    def has_any_klines(self, symbol: str) -> bool:
        """
        @brief Whether a symbol's shard holds at least one kline, in any interval.
        """
        if not self.db_manager.has_shard(symbol):
            return False
        with self.db_manager.get_session(symbol) as session:
            row = session.query(KlineModel.symbol).filter_by(symbol=symbol).first()
            return row is not None
