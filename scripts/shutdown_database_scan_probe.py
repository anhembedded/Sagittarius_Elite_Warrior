"""Process-level shutdown probe for an in-flight database scan (BUG-041)."""

from __future__ import annotations

import logging
from threading import Event
from time import sleep
from unittest.mock import Mock

from sagittarius_engine.infrastructure.thread_manager import ThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    DatabaseStatusSnapshot,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases.handler import (
    ScanAllDatabasesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases.query import (
    ScanAllDatabasesQuery,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

_SYMBOL_COUNT = 2_000
_SYMBOL_DELAY_SECONDS = 0.05
_START_TIMEOUT_SECONDS = 3.0
_FINISH_TIMEOUT_SECONDS = 3.0
_SUCCESS_MARKER = "SHUTDOWN_DATABASE_SCAN_PROBE_OK"


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s"
    )
    scan_started = Event()
    repository = Mock()

    def slow_status_for_intervals(
        _symbol: str, intervals: list[TimeFrame], *_args, **_kwargs
    ) -> dict[str, DatabaseStatusSnapshot]:
        # BUG-078: the handler now opens one call per symbol (covering every
        # requested interval), not one call per (symbol, interval) pair —
        # matches the real ScanAllDatabasesQueryHandler shape.
        scan_started.set()
        sleep(_SYMBOL_DELAY_SECONDS)
        empty = DatabaseStatusSnapshot(
            first_record=None,
            last_record=None,
            total_candles=0,
            gaps=0,
        )
        return {interval.value: empty for interval in intervals}

    repository.get_database_status_for_intervals.side_effect = slow_status_for_intervals
    handler = ScanAllDatabasesQueryHandler(repository)
    cancellation = CancellationToken()
    query = ScanAllDatabasesQuery(
        symbols=[f"SYMBOL_{index}" for index in range(_SYMBOL_COUNT)],
        intervals=["1m"],
        cancellation_requested=cancellation.is_cancelled,
    )
    thread_manager = ThreadManager(max_workers=1)
    future = thread_manager.submit(handler.execute, query)

    if not scan_started.wait(_START_TIMEOUT_SECONDS):
        raise RuntimeError("Database scan did not start")

    cancellation.cancel()
    thread_manager.shutdown(wait=False)
    future.result(timeout=_FINISH_TIMEOUT_SECONDS)
    print(_SUCCESS_MARKER, flush=True)


if __name__ == "__main__":
    main()
