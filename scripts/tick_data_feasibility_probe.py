"""BOT-075 spike probe: real cost of `1s` tick data vs `1m`, same 7-day window.

Standalone script, not a test — see Tasks/backlog/BOT-075_tick_data_feasibility_spike.md
and Tasks/reports/tick_data_feasibility.md for the task and the report this feeds.

Fetches BTCUSDT klines from Binance (public REST `/api/v3/klines`, no API key
needed) at `1s` and `1m` for the same 7-day window, saves each into an isolated
spike DB shard under `database/` (gitignored, kept as a fixture for BOT-076 —
do not re-sync casually, this burns real API weight), then times a range query
and an actual `RunStaticBacktestCommandHandler` run against the `1s` shard
(reuses the data already fetched — no extra API calls for that part).

Run from the superproject root with the venv Python:
    PYTHONPATH=. Sagittarius_Elite_Warrior/.venv/bin/python \
        Sagittarius_Elite_Warrior/scripts/tick_data_feasibility_probe.py
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (
    MemoryEventBus,
)

from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.event_publisher_adapter import (
    EngineEventPublisher,
)

from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.command import (
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.handler import (
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.binance.client import (
    PythonBinanceClient,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.database_manager import (
    DatabaseConfig,
    DatabaseManager,
)
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.sqlalchemy_repository import (
    SQLAlchemyMarketDataRepository,
)

SYMBOL = "BTCUSDT"
# Matches the app's own default (binance_bot_module.py: os.path.join(os.getcwd(),
# "database")) when run with cwd=Sagittarius_Elite_Warrior — pinned here instead of
# relying on cwd so this script writes to the same fixture location regardless of
# where it's invoked from.
_BOT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(_BOT_ROOT, "database")
RESULTS_PATH = os.path.join(_BOT_ROOT, "scratch_tick_feasibility_results.json")

RUNS = [
    ("1s", TimeFrame.ONE_SECOND, "BTCUSDT_1S_SPIKE"),
    ("1m", TimeFrame.ONE_MINUTE, "BTCUSDT_1M_SPIKE"),
]


def main() -> None:
    end = datetime.now(UTC).replace(microsecond=0)
    start = end - timedelta(days=7)
    print(f"Window: {start.isoformat()} -> {end.isoformat()} ({SYMBOL})")

    client = PythonBinanceClient()
    db_manager = DatabaseManager(DatabaseConfig(db_dir=DB_DIR))
    repo = SQLAlchemyMarketDataRepository(db_manager)

    results: dict[str, object] = {}

    for label, interval, spike_symbol in RUNS:
        print(f"\n=== {label} ===")

        t0 = time.perf_counter()
        klines = client.get_historical_klines(SYMBOL, interval, start, end)
        fetch_s = time.perf_counter() - t0
        rate = len(klines) / fetch_s if fetch_s > 0 else float("inf")
        print(f"Fetched {len(klines)} klines in {fetch_s:.2f}s ({rate:.0f}/s)")

        renamed = [replace(k, symbol=spike_symbol) for k in klines]
        t0 = time.perf_counter()
        repo.save_klines(renamed)
        save_s = time.perf_counter() - t0
        print(f"Saved in {save_s:.2f}s")

        db_path = os.path.join(DB_DIR, f"{spike_symbol}.db")
        size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        print(f"DB file size: {size_bytes / 1024 / 1024:.2f} MiB ({db_path})")

        t0 = time.perf_counter()
        queried = repo.get_klines(
            symbol=spike_symbol,
            interval=interval,
            start_time=start,
            end_time=end,
        )
        query_s = time.perf_counter() - t0
        print(f"Query returned {len(queried)} rows in {query_s * 1000:.1f}ms")

        results[label] = {
            "count": len(klines),
            "fetch_seconds": fetch_s,
            "save_seconds": save_s,
            "db_size_bytes": size_bytes,
            "query_seconds": query_s,
        }

    print("\n=== Static backtest runtime on the 1s shard (no extra API calls) ===")
    registry = StrategyRegistry()
    registry.register("ema_crossover", EmaCrossoverStrategy)
    handler = RunStaticBacktestCommandHandler(
        repo, registry, EngineEventPublisher(MemoryEventBus())
    )
    command = RunStaticBacktestCommand(
        symbol="BTCUSDT_1S_SPIKE",
        interval=TimeFrame.ONE_SECOND,
        strategy_key="ema_crossover",
        start_time=start,
        end_time=end,
    )
    t0 = time.perf_counter()
    result = handler.execute(command)
    backtest_s = time.perf_counter() - t0
    trade_count = (
        len(result.trades) if result is not None and hasattr(result, "trades") else None
    )
    print(
        f"RunStaticBacktestCommandHandler.execute() took {backtest_s:.2f}s, trades={trade_count}"
    )

    results["1s_backtest_seconds"] = backtest_s
    results["1s_backtest_trades"] = trade_count

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nWrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
