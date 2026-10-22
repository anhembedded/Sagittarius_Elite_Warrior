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
  period's candles (and its 1-second klines within `FINE_KLINES_MAX_PERIOD`), then runs the same backtest again; "Stop" leaves what it
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
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.candle_drawing import (
    CandleDrawing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.candle_preview import (
    CandlePreview,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.candle_window import (
    sync_requests,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.outcome_shown import (
    outcome_shown,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.outcome_view import (
    missing_candles,
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
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.sync_offer import (
    sync_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_failure import (
    failure_notice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_selection import (
    WorkbenchSelection,
    request_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_state import (
    WorkbenchState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks import (
    plan_checks_of,
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
        preview: CandlePreview,
    ) -> None:
        super().__init__(view)
        self._view = view
        self._coordinator = coordinator
        #: Whether the sync in flight was a run's offer (it runs again) or the candles' (read again).
        self._rerun_after_sync = False
        self._notifier = notifier
        self._tracker: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._sandbox = SandboxEditing(view, kinds)
        self._candles = CandleDrawing(
            view,
            preview,
            self._sandbox,
            notifier,
            lambda: self._outcome is not None,
            self._refresh,
        )
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
        view.window_changed.connect(self._refresh)
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
        self._candles.close()
        self._view.shutdown()

    # -- the sandbox -------------------------------------------------------- #

    def _restart(self) -> None:
        """A new source: whatever ran ends and the result of another bot is gone."""
        self._stop()
        self._outcome = self._refusal = self._last = None
        self._note = ""
        self._candles.forget()
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
        """After a refusal for missing funding history: runs, and the result says it is not included (`EPIC-039K`)."""
        self._start_run(FundingRequirement.OPTIONAL)

    def _start_run(self, funding: FundingRequirement) -> None:
        if self._busy() or self._why_not():
            return
        query = self._build_query(funding)
        if query is None:
            return
        self._last = query
        self._refusal, self._note = None, ""
        action = self._tracker.begin_action(_KIND, "backtest", None)
        self._activity = next_activity(self._activity, RunEvent.RUN_STARTED)
        request = query.request
        logger.info(
            "Backtest %s: %s %s %s to %s",
            action.action_id,
            query.kind_id,
            request.symbol,
            request.interval.value,
            request.end,
        )
        self._refresh()
        self._coordinator.start_backtest(action.action_id, query)

    def _on_sync_requested(self) -> None:
        drawn = self._candles.wanted
        offer = sync_plan(self._last, self._refusal, self._outcome, drawn)
        if self._busy() or offer is None:
            return
        self._rerun_after_sync = offer.then_run
        action = self._tracker.begin_action(_KIND, "sync", None)
        self._activity = next_activity(self._activity, RunEvent.SYNC_STARTED)
        self._refusal, self._note = None, ""
        logger.info("Backtest %s: syncing %s", action.action_id, offer.window.symbol)
        self._refresh()
        self._coordinator.start_sync(action.action_id, sync_requests(offer.window))

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
            self._after_sync()
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

    def _after_sync(self) -> None:
        """A run's sync runs it again with the funding the person chose (a run started without funding
        is not turned into one that demands it); the candles' sync reads them again."""
        query = self._last
        if self._rerun_after_sync and query is not None:
            self._start_run(query.request.funding)
        else:
            self._candles.reload()
            self._refresh()

    def _show_outcome(self, outcome: BacktestOutcome) -> None:
        self._outcome, self._refusal, self._note = outcome, None, ""
        query, plan = self._last, self._sandbox.plan
        if query is not None and plan is not None:
            self._view.show_outcome(
                outcome_shown(outcome, query.request, plan, self._sandbox.kind())
            )

    # -- what the page says ---------------------------------------------------- #

    def _state(self) -> WorkbenchState:
        plan = self._sandbox.plan
        has_sandbox = self._selection.bot is not None and plan is not None
        pending = self._sandbox.pending_copy
        refusal, outcome = self._refusal, self._outcome
        missing = missing_candles(outcome)
        found = self._candles.found
        verdicts = self._sandbox.verdicts
        return WorkbenchState(
            activity=self._activity,
            reason=self._why_not(),
            status=self._status(missing),
            offer_sync=bool(refusal and refusal.missing_candles)
            or bool(missing)
            or (found is not None and found.needs_sync),
            candles_text=self._candles.stored_line,
            offer_without_funding=bool(refusal and refusal.funding_unavailable),
            has_sandbox=has_sandbox,
            changed_fields=plan.changed_fields() if plan is not None else (),
            source_text=source_text(plan, self._world.market) if has_sandbox else "",
            question=words.DISCARD_QUESTION if pending is not None else "",
            checks=plan_checks_of(
                tuple(v for v in verdicts if v.code not in UNCHECKED_CODES)
            ),
            unchecked_lines=tuple(
                sandbox_line(v) for v in verdicts if v.code in UNCHECKED_CODES
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

    def _build_query(self, funding: FundingRequirement) -> RunBacktestQuery | None:
        plan, window = self._sandbox.plan, self._candles.window()
        if plan is None:
            return None
        if window is None:
            self._refusal = BacktestRefusal(words.PERIOD_ORDER)
            self._refresh()
            return None
        request = request_of(self._world, plan, window, funding)
        return RunBacktestQuery(plan.kind_id, request) if request else None

    def _refresh(self) -> None:
        self._candles.follow()
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
