"""`BOT-095G` — `logic/session_run_history.py`.

Pure logic, no Qt: a plain dataclass, a factory function taking `now` as a
parameter (`BUG-123`'s clock-testability precedent), and an in-memory ring
buffer. Every assertion below constructs the real types directly.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_metrics import (
    BacktestMetrics,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.session_run_history import (
    SessionRunHistoryCache,
    make_run_snapshot,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 1, 2, tzinfo=UTC)


def _run_config(symbol: str = "ETHUSDT") -> BacktestRunConfig:
    return BacktestRunConfig(
        strategy_key="ema_crossover",
        timeframe=TimeFrame.FIVE_MINUTES,
        initial_balance=10_000.0,
        start_time=None,
        end_time=None,
        symbol=symbol,
    )


def _result(net_profit_percent: float = 12.5) -> BacktestResult:
    metrics = BacktestMetrics.compute([], [(_T0, 1000.0), (_T1, 1000.0)], 1000.0)
    metrics = replace(metrics, net_profit_percent=net_profit_percent)
    return BacktestResult(
        symbol="ETHUSDT",
        initial_balance=1000.0,
        final_balance=1000.0 * (1 + net_profit_percent / 100),
        trades=[],
        equity_curve=[(_T0, 1000.0), (_T1, 1000.0)],
        metrics=metrics,
    )


def _snapshot(now: datetime, symbol: str = "ETHUSDT", net_profit_percent: float = 12.5):
    return make_run_snapshot(
        form_data={"selectedSymbol": symbol},
        run_config=_run_config(symbol),
        result=_result(net_profit_percent),
        klines=[{"t": 1}],
        volume=[{"t": 1, "v": 2}],
        now=now,
    )


def test_make_run_snapshot_uses_the_given_now_not_the_wall_clock():
    fixed_now = datetime(2026, 3, 1, 15, 20, tzinfo=UTC)
    snapshot = _snapshot(fixed_now)

    assert snapshot.timestamp == fixed_now


def test_make_run_snapshot_assigns_a_unique_run_id_per_call():
    now = datetime(2026, 3, 1, tzinfo=UTC)
    first = _snapshot(now)
    second = _snapshot(now)

    assert first.run_id != second.run_id


def test_snapshot_label_includes_time_config_and_signed_pnl():
    now = datetime(2026, 1, 1, 15, 20, 5, tzinfo=UTC)
    snapshot = _snapshot(now, net_profit_percent=28.4)

    label = snapshot.label

    assert "15:20:05" in label
    assert "ETHUSDT" in label
    assert "+28.4%" in label


def test_snapshot_label_shows_negative_pnl_without_a_leading_plus():
    snapshot = _snapshot(datetime(2026, 1, 1, tzinfo=UTC), net_profit_percent=-9.1)

    assert "-9.1%" in snapshot.label
    assert "+-9.1%" not in snapshot.label


def test_cache_get_all_returns_newest_first():
    cache = SessionRunHistoryCache()
    older = _snapshot(datetime(2026, 1, 1, tzinfo=UTC), symbol="ETHUSDT")
    newer = _snapshot(datetime(2026, 1, 2, tzinfo=UTC), symbol="BTCUSDT")

    cache.push(older)
    cache.push(newer)

    assert cache.get_all() == (newer, older)


def test_cache_evicts_the_oldest_entry_beyond_max_history():
    cache = SessionRunHistoryCache()
    snapshots = [
        _snapshot(datetime(2026, 1, i + 1, tzinfo=UTC), symbol=f"SYM{i}")
        for i in range(SessionRunHistoryCache.MAX_HISTORY + 2)
    ]

    for snapshot in snapshots:
        cache.push(snapshot)

    all_entries = cache.get_all()
    assert len(all_entries) == SessionRunHistoryCache.MAX_HISTORY
    # Newest-first: the two oldest pushes (index 0, 1) must be the ones gone.
    kept_ids = {s.run_id for s in all_entries}
    assert snapshots[0].run_id not in kept_ids
    assert snapshots[1].run_id not in kept_ids
    assert snapshots[-1].run_id in kept_ids


def test_cache_get_by_id_finds_a_pushed_snapshot():
    cache = SessionRunHistoryCache()
    snapshot = _snapshot(datetime(2026, 1, 1, tzinfo=UTC))
    cache.push(snapshot)

    assert cache.get_by_id(snapshot.run_id) is snapshot


def test_cache_get_by_id_returns_none_for_an_evicted_or_unknown_id():
    cache = SessionRunHistoryCache()
    cache.push(_snapshot(datetime(2026, 1, 1, tzinfo=UTC)))

    assert cache.get_by_id("not-a-real-id") is None


def test_cache_clear_empties_the_history():
    cache = SessionRunHistoryCache()
    cache.push(_snapshot(datetime(2026, 1, 1, tzinfo=UTC)))

    cache.clear()

    assert cache.get_all() == ()
