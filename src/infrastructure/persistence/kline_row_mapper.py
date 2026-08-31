"""`EPIC-018B` — ORM-row/domain-entity mapping and raw SQL query building,
pulled out of `SQLAlchemyMarketDataRepository`: that class mixed three
abstraction levels (raw SQL text, ORM-row-to-entity mapping, and repository
orchestration) in one 478-line file, past the >400-line hard threshold in
`architecture-rule.md` §5.4. Plain module-level functions, matching the
precedent this same repository file already imports from
(`application/services/backtest_range_coverage.py`'s `as_utc`/
`ceil_open_time`/`floor_open_time`) rather than a class with no state to
hold.

The repository class keeps only orchestration: open a session, call one of
these, return the result. Nothing here touches `DatabaseManager` or a
`Session` — every function is either pure or takes its raw SQL result in
and hands a domain object back.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.models import KlineModel
from sqlalchemy.dialects.sqlite import insert


def to_market_data_entity(row: KlineModel) -> MarketData:
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


def parse_db_datetime(value: Any) -> datetime | None:
    """Normalizes a raw SQLite datetime result to a UTC-aware datetime.

    SQLite may return either a native datetime (typed column) or an ISO
    string (raw SQL aggregate result, as used by the status/coverage/gap
    queries below) depending on the query path — this handles both.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC)
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def build_upsert_stmt() -> Any:
    """Builds the SQLite-dialect ON CONFLICT DO UPDATE statement for `KlineModel`."""
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


def build_status_query() -> sa.TextClause:
    # We use a CTE with LAG to compute the previous candle time, then
    # aggregate in the outer query. Runs entirely inside SQLite, preventing
    # OOM on a full-shard scan.
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


def map_status_result(result: tuple | None) -> DatabaseStatusSnapshot:
    if not result or result[2] == 0:
        return DatabaseStatusSnapshot(
            first_record=None,
            last_record=None,
            total_candles=0,
            gaps=0,
        )

    return DatabaseStatusSnapshot(
        first_record=parse_db_datetime(result[0]),
        last_record=parse_db_datetime(result[1]),
        total_candles=result[2],
        gaps=result[3] if result[3] is not None else 0,
    )


def build_range_coverage_query() -> sa.TextClause:
    return sa.text("""
        WITH ordered_klines AS (
            SELECT
                open_time,
                close_time,
                LAG(open_time) OVER (ORDER BY open_time ASC) AS prev_time
            FROM klines
            WHERE symbol = :symbol
              AND interval = :interval
              AND (:start_time IS NULL OR open_time >= :start_time)
              AND open_time < :closed_end
        )
        SELECT
            MIN(open_time) AS first_record,
            MAX(open_time) AS last_record,
            COUNT(*) AS total_candles,
            COUNT(DISTINCT open_time) AS distinct_candles,
            MIN(CASE
                WHEN prev_time IS NOT NULL
                 AND (unixepoch(open_time) - unixepoch(prev_time)) > :expected_seconds
                THEN prev_time ELSE NULL
            END) AS first_gap_after,
            SUM(CASE WHEN close_time > :now THEN 1 ELSE 0 END) AS unclosed_candles
        FROM ordered_klines
    """)


def build_gaps_query() -> sa.TextClause:
    return sa.text("""
        WITH ordered_klines AS (
            SELECT
                open_time,
                LAG(open_time) OVER (ORDER BY open_time ASC) AS prev_time
            FROM klines
            WHERE symbol = :symbol
              AND interval = :interval
        )
        SELECT
            prev_time AS gap_start,
            open_time AS gap_end,
            CAST((unixepoch(open_time) - unixepoch(prev_time) - :expected_seconds) / :expected_seconds AS INTEGER) AS missing_candles
        FROM ordered_klines
        WHERE prev_time IS NOT NULL
          AND (unixepoch(open_time) - unixepoch(prev_time)) > :expected_seconds
        ORDER BY prev_time ASC
    """)
