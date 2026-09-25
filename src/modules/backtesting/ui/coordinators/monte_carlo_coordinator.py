"""Running `BOT-107B`'s Monte Carlo trade-reshuffling simulation off the Qt
thread — 5,000-10,000 shuffles of a real run's trades is cheap in wall-clock
terms for a typical trade count, but `ui-presentation-rule.md` §2's "the UI
thread never blocks" applies regardless of how fast a given case happens to
be.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from random import Random

from ...contracts.monte_carlo_simulation import (
    MonteCarloSimulationResult,
    run_monte_carlo_simulation,
)
from ...contracts.trade import Trade

logger = logging.getLogger("App.BackTestPresenter")


class MonteCarloCoordinator:
    """Owns dispatching one Monte Carlo run to a background thread and
    reporting its outcome back — no FSM state, no action-id bookkeeping of
    its own (`async-ui-action-rule.md` §2). `run_id` is presenter-owned and
    handed in, the same shape `ChartPreviewCoordinator`'s own
    `next_preview_id`/`active_preview_id` pair already establishes for an
    independent, secondary async concern that isn't the screen's main FSM
    action: a stale result from a superseded run must never overwrite a
    newer one.
    """

    def __init__(
        self,
        thread_manager,
        emit_completed: Callable[[int, MonteCarloSimulationResult], None],
        emit_failed: Callable[[int, str], None],
    ) -> None:
        self._thread_manager = thread_manager
        self._emit_completed = emit_completed
        self._emit_failed = emit_failed

    def run(
        self,
        trades: Sequence[Trade],
        initial_balance: float,
        iterations: int,
        run_id: int,
    ) -> None:
        self._thread_manager.submit(
            self._run_worker, trades, initial_balance, iterations, run_id
        )

    def _run_worker(
        self,
        trades: Sequence[Trade],
        initial_balance: float,
        iterations: int,
        run_id: int,
    ) -> None:
        """Background method — submitted to `IThreadManager`. MUST NOT touch
        the view model directly; signals only, via the injected callables."""
        try:
            result = run_monte_carlo_simulation(
                trades,
                initial_balance,
                iterations,
                Random(),  # noqa: S311 — Monte Carlo sampling, not cryptography
            )
        except Exception as exc:
            logger.exception("Monte Carlo simulation failed")
            self._emit_failed(run_id, str(exc))
            return
        self._emit_completed(run_id, result)
