"""`EPIC-040D` — the Backtest workbench's presenter: one sandbox, one run at a time, any kind.

Owns the one tracker for the page's background work (`async-ui-action-rule.md` §1): a backtest and a
candle sync are each an action with its own id, the coordinator answers with that id, and an answer
whose action is no longer the current one is dropped and logged. So:
· **Cancel** invalidates the action before it stops the worker: a cancelled run publishes nothing, and
  the last result stays on screen (the state before the run, never a blank).
· **Another bot selected** ends the run the same way and clears the result: a result is only ever shown
  beside the bot it was run for. A bot whose edits would be thrown away asks first (`SandboxSession`);
  until the answer the sandbox stays the source bot's, judged and replayed with the market numbers
  that bot came with (`_world`), and a run in flight finishes for it.
· **Sync** (offered only after a refusal for candles that are not stored, `BUG-107`) fetches the
  period's candles and its 1-second klines, then runs the same backtest again; "Stop" leaves what it
  stored.

What the page says is built from the facts in one place (`_state`), so no sentence outlives the state
that wrote it. The sandbox is judged by the kind's own `validate` with no account (`judge_sandbox`);
a plan the symbol's rules refuse is not replayed.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    INotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_backtest import (
    RunBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    KindBacktestRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_answer import (
    BacktestCancelled,
    BacktestRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.funding_requirement import (
    FundingRequirement,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest.sandbox_judge import (
    UNCHECKED_CODES,
    sandbox_line,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest.sandbox_session import (
    SandboxFollow,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench import (
    workbench_words as words,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_run_coordinator import (
    BacktestRunCoordinator,
    RunAnswer,
    Synced,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_run_fsm_matrix import (
    RunActivity,
    RunEvent,
    next_activity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
    OutcomeShown,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.outcome_view import (
    chart_candles,
    figure_readout,
    missing_candles,
    result_overlay,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.run_gate import (
    reason_run_is_off,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.sandbox_editing import (
    KindSources,
    SandboxEditing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.source_line import (
    source_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_failure import (
    failure_notice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_selection import (
    WorkbenchSelection,
    sync_requests,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_state import (
    WorkbenchState,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)

logger = logging.getLogger("App.Bots.Backtest")

_KIND = "backtest_workbench"


class BacktestWorkbenchPresenter(QObject):
    """@brief Runs, cancels and shows one backtest of one sandbox at a time."""

    def __init__(
        self,
        view: BacktestWorkbenchView,
        coordinator: BacktestRunCoordinator,
        notifier: INotifier,
        kinds: KindSources,
    ) -> None:
        super().__init__(view)
        self._view = view
        self._coordinator = coordinator
        self._notifier = notifier
        self._tracker: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._sandbox = SandboxEditing(view, kinds)
        self._selection = WorkbenchSelection()
        #: The selection the sandbox's source bot came with: the market numbers and risk facts it is
        #: judged and replayed by. Another bot's numbers never replace them while the sandbox keeps
        #: this bot's edited plan (review of `EPIC-040D`, round 1).
        self._world = WorkbenchSelection()
        self._activity = RunActivity.IDLE
        self._last: RunBacktestQuery | None = None
        self._outcome: BacktestOutcome | None = None
        self._refusal: BacktestRefusal | None = None
        self._note = ""
        view.run_requested.connect(self._on_run_requested)
        view.cancel_requested.connect(self._on_cancel_requested)
        view.sync_requested.connect(self._on_sync_requested)
        view.run_without_funding_requested.connect(self._on_run_without_funding)
        view.reset_requested.connect(self._on_reset)
        view.replace_edits_requested.connect(self._on_replace_edits)
        view.keep_edits_requested.connect(self._on_keep_edits)
        view.config_edited.connect(self._on_config_edited)
        coordinator.finished.connect(self._on_finished)
        self._refresh()

    def follow(self, selection: WorkbenchSelection) -> None:
        """The Bots screen calls this on every refresh of the selection (its clock, each planner
        answer), so only a new source (another bot, the same bot saved anew) restarts the page."""
        self._selection = selection
        followed = self._sandbox.follow(selection)
        if followed is SandboxFollow.COPIED:
            self._world = selection
            self._restart()
        elif self._sandbox.copies(selection):
            self._world = selection
        self._sandbox.judge(self._world)
        self._refresh()

    def shutdown(self) -> None:
        self._stop()
        self._coordinator.close()
        self._view.shutdown()

    # -- the sandbox -------------------------------------------------------- #

    def _restart(self) -> None:
        """A new source: whatever ran ends and the result of another bot is gone."""
        self._stop()
        self._outcome = self._refusal = self._last = None
        self._note = ""
        self._view.clear_result()
        self._sandbox.show_copy()

    def _on_config_edited(self, config: Mapping[str, str]) -> None:
        if self._sandbox.plan is not None:
            self._sandbox.edit(config)
            self._sandbox.judge(self._world)
            self._refresh()

    def _on_reset(self) -> None:
        self._sandbox.reset()
        self._sandbox.judge(self._world)
        self._refresh()

    def _on_replace_edits(self) -> None:
        self._sandbox.confirm_switch()
        self._world = self._selection
        self._restart()
        self._sandbox.judge(self._world)
        self._refresh()

    def _on_keep_edits(self) -> None:
        self._sandbox.keep_current()
        self._refresh()

    # -- commands ------------------------------------------------------------ #

    def _on_run_requested(self) -> None:
        self._start_run(FundingRequirement.REQUIRED)

    def _on_run_without_funding(self) -> None:
        """The user's explicit choice after a refusal for missing funding history: the replay runs
        and its result says funding is not included (`EPIC-039K`, O9)."""
        self._start_run(FundingRequirement.OPTIONAL)

    def _start_run(self, funding: FundingRequirement) -> None:
        if self._busy() or self._why_not():
            return
        request = self._build_request(funding)
        plan = self._sandbox.plan
        if request is None or plan is None:
            return
        query = RunBacktestQuery(plan.kind_id, request)
        self._last = query
        self._refusal, self._note = None, ""
        action = self._tracker.begin_action(_KIND, "backtest", None)
        self._activity = next_activity(self._activity, RunEvent.RUN_STARTED)
        logger.info(
            "Backtest %s: %s %s %s to %s",
            action.action_id,
            plan.kind_id,
            request.symbol,
            request.interval.value,
            request.end,
        )
        self._refresh()
        self._coordinator.start_backtest(action.action_id, query)

    def _on_sync_requested(self) -> None:
        query = self._last
        if self._busy() or query is None:
            return
        action = self._tracker.begin_action(_KIND, "sync", None)
        self._activity = next_activity(self._activity, RunEvent.SYNC_STARTED)
        self._refusal, self._note = None, ""
        logger.info("Backtest %s: syncing %s", action.action_id, query.request.symbol)
        self._refresh()
        self._coordinator.start_sync(action.action_id, sync_requests(query.request))

    def _on_cancel_requested(self) -> None:
        if not self._busy():
            return  # a shortcut or a menu command can reach this with nothing running
        label = self._active_label()
        self._stop(RunEvent.CANCELLED)
        self._refusal = None
        self._note = words.SYNC_STOPPED if label == "sync" else words.CANCELLED
        self._refresh()

    # -- answers -------------------------------------------------------------- #

    def _on_finished(self, action_id: int, answer: RunAnswer, detail: str) -> None:
        if not self._tracker.is_current_pending(action_id, _KIND):
            self._tracker.log_stale_callback("_on_finished", action_id, _KIND)
            return
        label = self._active_label()
        failed = bool(detail)
        self._tracker.finish_action(
            action_id, ActionOutcome.FAILED if failed else ActionOutcome.SUCCEEDED
        )
        self._activity = next_activity(
            self._activity, RunEvent.FAILED if failed else RunEvent.ANSWERED
        )
        if failed:
            self._refusal = BacktestRefusal(words.RUN_FAILED)
            self._notifier.report_failure(failure_notice(label, detail))
        elif isinstance(answer, Synced):
            self._refresh()
            self._rerun_after_sync()
            return
        elif isinstance(answer, BacktestOutcome):
            self._show_outcome(answer)
        elif isinstance(answer, BacktestRefusal):
            self._refusal = answer
        elif isinstance(answer, BacktestCancelled):
            self._note = words.CANCELLED
        else:
            logger.error(
                "Backtest %s ended with an answer nobody reads: %r", action_id, answer
            )
            self._refusal = BacktestRefusal(words.RUN_FAILED)
        self._refresh()

    def _rerun_after_sync(self) -> None:
        """The same query again with the funding the person chose for it: a run they started
        without funding is not turned back into one that demands it."""
        query = self._last
        if query is not None:
            self._start_run(query.request.funding)

    def _show_outcome(self, outcome: BacktestOutcome) -> None:
        self._outcome, self._refusal, self._note = outcome, None, ""
        query, plan = self._last, self._sandbox.plan
        market = self._world.market
        kind = self._sandbox.kind()
        if query is None or plan is None:
            return
        overlay = BotOverlay()
        if kind is not None and market is not None and market.terms is not None:
            overlay = result_overlay(kind, plan, market.terms, outcome)
        request = query.request
        self._view.show_outcome(
            OutcomeShown(
                chart_candles(outcome, request.symbol, request.interval),
                overlay,
                outcome.equity,
                figure_readout(outcome),
                outcome.notes,
                outcome.fills,
            )
        )

    # -- what the page says ---------------------------------------------------- #

    def _state(self) -> WorkbenchState:
        plan = self._sandbox.plan
        has_sandbox = self._selection.bot is not None and plan is not None
        pending = self._sandbox.pending_copy
        refusal, outcome = self._refusal, self._outcome
        missing = missing_candles(outcome)
        return WorkbenchState(
            activity=self._activity,
            reason=self._why_not(),
            status=self._status(missing),
            offer_sync=bool(refusal and refusal.missing_candles) or bool(missing),
            offer_without_funding=bool(refusal and refusal.funding_unavailable),
            has_sandbox=has_sandbox,
            changed_fields=plan.changed_fields() if plan is not None else (),
            source_text=source_text(plan, self._world.market) if has_sandbox else "",
            question=words.DISCARD_QUESTION if pending is not None else "",
            verdict_lines=tuple(
                sandbox_line(v)
                for v in self._sandbox.verdicts
                if v.severity is not VerdictSeverity.OK or v.code in UNCHECKED_CODES
            ),
        )

    def _status(self, missing: int) -> str:
        query = self._last
        symbol = query.request.symbol if query is not None else ""
        interval = query.request.interval.value if query is not None else ""
        if self._activity is RunActivity.RUNNING:
            return words.running(symbol, interval)
        if self._activity is RunActivity.SYNCING:
            return words.syncing(symbol, interval)
        if self._note:
            return self._note
        if self._refusal is not None:
            return self._refusal.reason
        if self._outcome is not None:
            return words.partly_stored(missing) if missing else words.DONE
        return self._why_not()

    def _why_not(self) -> str:
        """Why Run is off; `""` when it is on."""
        return reason_run_is_off(self._selection, self._world, self._sandbox)

    def _build_request(self, funding: FundingRequirement) -> KindBacktestRequest | None:
        plan, market = self._sandbox.plan, self._world.market
        if plan is None or market is None or market.terms is None:
            return None
        start, end = self._view.chosen_period()
        if end <= start:
            self._refusal = BacktestRefusal(words.PERIOD_ORDER)
            self._refresh()
            return None
        risk = self._world.risk
        return KindBacktestRequest(
            plan.symbol,
            plan.config,
            market.terms,
            self._view.chosen_interval(),
            start,
            end,
            plan.venue,
            brackets=risk.brackets if risk is not None else None,
            funding=funding,
        )

    def _refresh(self) -> None:
        self._view.show_state(self._state())

    def _busy(self) -> bool:
        return self._tracker.active_outcome is ActionOutcome.PENDING

    def _active_label(self) -> str:
        active = self._tracker.active_action
        return active.config if active is not None and self._busy() else ""

    def _stop(self, event: RunEvent = RunEvent.SELECTION_CHANGED) -> None:
        if self._busy():
            self._tracker.invalidate_active()
            self._coordinator.stop()
        self._activity = next_activity(self._activity, event)
