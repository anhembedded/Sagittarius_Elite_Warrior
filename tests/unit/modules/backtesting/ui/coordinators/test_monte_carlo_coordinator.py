"""`MonteCarloCoordinator` — dispatch to a background thread, report back
via callables, fence nothing itself (`run_id` bookkeeping is the
presenter's job, per `async-ui-action-rule.md` §2 — this test only proves
the coordinator forwards whatever `run_id` it was given, faithfully)."""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.coordinators.monte_carlo_coordinator import (
    MonteCarloCoordinator,
)

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


class _SynchronousThreadManager:
    """Derived from `IThreadManager.submit(task, *args, **kwargs)`'s own
    signature — runs the task immediately rather than on a real worker
    thread, so a test can assert on the outcome without waiting."""

    def submit(self, task, *args, **kwargs):
        task(*args, **kwargs)


def _trade(pnl: float) -> Trade:
    return Trade(
        symbol="BTCUSDT",
        entry_time=_T0,
        entry_price=100.0,
        exit_time=_T0,
        exit_price=100.0,
        quantity=1.0,
        pnl=pnl,
        pnl_percent=pnl / 10.0,
        fees_paid=0.0,
    )


def _build():
    completed: list[tuple[int, object]] = []
    failed: list[tuple[int, str]] = []
    coordinator = MonteCarloCoordinator(
        thread_manager=_SynchronousThreadManager(),
        emit_completed=lambda run_id, result: completed.append((run_id, result)),
        emit_failed=lambda run_id, message: failed.append((run_id, message)),
    )
    return coordinator, completed, failed


def test_a_successful_run_emits_completed_with_the_given_run_id():
    coordinator, completed, failed = _build()
    trades = [_trade(10.0), _trade(-5.0), _trade(20.0)]

    coordinator.run(trades, initial_balance=1000.0, iterations=200, run_id=7)

    assert failed == []
    assert len(completed) == 1
    run_id, result = completed[0]
    assert run_id == 7
    assert result.iterations == 200


def test_a_failing_run_emits_failed_with_the_given_run_id_instead_of_raising():
    coordinator, completed, failed = _build()

    # No trades at all is `run_monte_carlo_simulation()`'s own guarded
    # failure mode (`ValueError`) — proves the coordinator's `try/except`
    # actually converts it into `emit_failed` rather than propagating.
    coordinator.run([], initial_balance=1000.0, iterations=200, run_id=3)

    assert completed == []
    assert len(failed) == 1
    run_id, message = failed[0]
    assert run_id == 3
    assert "at least one closed trade" in message
