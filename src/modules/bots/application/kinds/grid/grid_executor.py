"""`EPIC-029E` — the actor that runs one Grid bot (ADR D9–D11, §3.1).

Every entry point **posts** to the bot's queue and returns: the commands from
the use cases (start, pause, resume, stop) here, and the facts from the
handlers (fills, ends, ticks, the switch, the stream) through `facts`
(`GridFacts`, the `IBotFacts` port). Only the queue's worker touches the bot's
record, submits, cancels and writes the store, so the ladder has one writer
and an event never interleaves with an order in flight.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_exposures import (
    GridExposure,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_facts import (
    GridFactParts,
    GridFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_ladder_placer import (
    GridLadderPlacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_parking import (
    GridParking,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_task_guard import (
    GridTaskGuard,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protection_spot import (
    NoProtection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_halt_recovery import (
    GridHaltRecovery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_reconciler import (
    GridReconciler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_recovery_reader import (
    GridRecoveryReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_resume_sequence import (
    GridResumeSequence,
    ResumeParts,
    ResumeProposal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.start.grid_interrupted_start import (
    GridInterruptedStart,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.start.grid_start_sequence import (
    GridStartSequence,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_mark_exit import (
    GridMarkExit,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stop_retry import (
    GridStopRetry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stop_sequence import (
    GridStopSequence,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stopper import (
    GridStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_halt_probe import (
    GridHaltProbe,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_key_probe import (
    GridKeyProbe,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_price_reaction import (
    GridPriceReaction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_rate_limit_pause import (
    GridRateLimitPause,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_storage_watch import (
    GridStorageWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_stream_gap import (
    GridStreamGap,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_terms_watch import (
    GridTermsWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.symbol_status_gate import (
    SymbolStatusGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
    IBotExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_facts import IBotFacts
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import plan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Bots.GridExecutor")

_S = BotLifecycleState
_E = BotLifecycleEvent

_SWITCH_OFF_DETAIL = {
    TradingSwitchCause.EMERGENCY_STOP: (
        "Emergency Stop cancelled every order and sold what was bought since "
        "the session opened"
    ),
}


class GridExecutor(IBotExecutor):
    """One Grid bot's actor: every call is queued and run in order."""

    def __init__(
        self,
        context: GridRunContext,
        queue: IBotWorkQueue,
        retries: IBotRetryScheduler,
        exposure: GridExposure,
    ) -> None:
        """@param exposure The collaborators of the venue profile's exposure: the
        opening, the close, the reconcile check, the order flags and, on a position venue,
        the risk watch (`EPIC-039H`)."""
        self._context = context
        self._queue = queue
        self._start = GridStartSequence(
            context,
            exposure.opening,
            exposure.flags,
            exposure.protection or NoProtection(),
        )
        self._stop = GridStopper(
            context,
            GridStopSequence(context, exposure.closer),
            GridStopRetry(context, retries, self._post),
            self._price,
        )
        self._status = SymbolStatusGate(context)
        self._storage = GridStorageWatch(context)
        self._resume = GridResumeSequence(
            context,
            ResumeParts(self._start, self._status, self._storage, exposure.check),
        )
        self._reconciler = GridReconciler(context, exposure.check)
        self._placer = GridLadderPlacer(context, exposure.flags)
        self._recovery = GridRecoveryReader(context)
        self._interrupted_start = GridInterruptedStart(context)
        self._gap = GridStreamGap(
            context, self._reconciler, self._placer.release_held, self._post
        )
        self._guard = GridTaskGuard(
            context,
            GridParking(context, exposure.closer, self._stop),
            GridRateLimitPause(context, retries, self._post, self._resume, self._price),
            self._storage,
        )
        self._prices = GridPriceReaction(
            context, self._stop, exits_on_mark=exposure.exit_marks is not None
        )
        self._proposal: ResumeProposal | None = None
        self._halt_recovery = GridHaltRecovery(
            context,
            context.halts,
            GridHaltProbe(context, context.streams),
            self._resume,
            self._stop,
            lambda: self._proposal is not None,
        )
        self._facts = GridFacts(
            context,
            GridFactParts(
                self._placer,
                self._prices,
                self._gap,
                self._stop,
                self._reconciler,
                self._interrupted_start,
                GridKeyProbe(context),
                GridTermsWatch(context),
                exposure.risk_watch,
                GridMarkExit(exposure.exit_marks, self._prices, self.bot_id)
                if exposure.exit_marks is not None
                else None,
                exposure.protection,
                self._halt_recovery,
            ),
            self._post,
            self._forget_proposal,
        )

    @property
    def bot_id(self) -> str:
        return self._context.state.bot_id

    @property
    def venue(self) -> TradingVenue:
        return self._context.state.bot.definition.venue

    @property
    def symbol(self) -> str:
        return self._context.state.bot.definition.symbol

    @property
    def proposal(self) -> ResumeProposal | None:
        """The ladder a resume from HALTED proposes, awaiting confirmation."""
        return self._proposal

    @property
    def facts(self) -> IBotFacts:
        """Where fills, ends, ticks, the switch and the stream report to this
        bot; each is queued behind the commands below (`GridFacts`)."""
        return self._facts

    def close(self) -> None:
        """Run what is queued, then stop the worker."""
        self._queue.close()

    # --- commands (IBotExecutor) ---

    def start(self) -> None:
        self._post("start", self._run_start)

    def pause(self) -> None:
        self._post("pause", self._run_pause)

    def resume(self) -> None:
        # The state the command was given in travels with it (`BUG-204`): a Resume asked
        # of a RECOVERING bot must not be read as another state's by the time it runs.
        asked_in = self._context.state.state
        self._post("resume", lambda: self._run_resume(asked_in))

    def stop(self, base: ExposureHandling) -> None:
        self._context.stop_requested.set()
        self._post("stop", lambda: self._run_stop(base))

    def confirm_resume(self) -> None:
        self._post("confirm resume", self._run_confirm)

    def recover_after_restart(self) -> None:
        """Boot: report what the exchange holds for a restored bot, and cancel
        what a cut-short start left; each step acts only if the bot is owed it."""
        self._post("restart recovery", self._recover)

    def has_resume_proposal(self) -> bool:
        """Read off the worker's thread: one reference, set and cleared by
        the worker alone; a confirmation that loses a race to a switch-off
        still finds nothing there and lays nothing (`_run_confirm`)."""
        return self._proposal is not None

    # --- every task through the guard ---

    def _post(self, what: str, task: Callable[[], None]) -> None:
        self._queue.post(lambda: self._guard.run(what, task))

    # --- on the worker ---

    def _run_start(self) -> None:
        state = self._context.state
        if state.state is not _S.STARTING:
            logger.info("Bot %s: start ignored in %s", self.bot_id, state.state.value)
            return
        if self._context.stop_requested.is_set():
            logger.info("Bot %s: Stop asked before the start began", self.bot_id)
            return
        if not self._status.admits():
            return
        price = self._price()
        self._start.run(
            plan(
                self._context.params,
                self._context.terms,
                price,
                self._context.level_sizing,
            )
        )

    def _run_stop(self, base: ExposureHandling) -> None:
        self._context.stop_requested.clear()
        self._stop.run(base, GridReason.USER_STOP)

    def _run_pause(self) -> None:
        self._transition_if_declared(_E.PAUSE)

    def _run_resume(self, asked_in: BotLifecycleState) -> None:
        state = self._context.state
        if asked_in is _S.RECOVERING and state.state is not _S.RECOVERING:
            # `BUG-204` - the session's own switch-on reconcile ran first and moved the
            # bot on (a mismatch halts it). That halt is for the owner to read; this
            # Resume was for leaving RECOVERING, and is not a HALTED bot's re-plan.
            logger.info(
                "Bot %s: resume from RECOVERING dropped, the bot is %s [recovering-resume]",
                self.bot_id,
                state.state.value,
            )
            return
        if state.state in RESUME_PROPOSES_STATES:
            self._proposal = self._resume.propose(self._price())
            return
        if state.state is _S.RECOVERING:
            # `BUG-204` - the runner opened the order session before queueing this; a
            # session that was already open sent no switch-on event, so reconcile here.
            self._facts.reconcile_recovering()
            return
        if state.state is not _S.PAUSED:
            logger.info("Bot %s: resume ignored in %s", self.bot_id, state.state.value)
            return
        if not self._storage.admits_resume() or not self._status.admits():
            return
        state.transition(_E.RESUME)
        self._storage.resumed()
        self._placer.release_held()

    def _run_confirm(self) -> None:
        proposal, self._proposal = self._proposal, None
        if self._context.state.state not in RESUME_PROPOSES_STATES or proposal is None:
            logger.info(
                "Bot %s: nothing to confirm in %s",
                self.bot_id,
                self._context.state.state.value,
            )
            return
        self._resume.confirm(proposal)

    def _forget_proposal(self) -> None:
        self._proposal = None

    def _recover(self) -> None:
        self._recovery.report()
        self._interrupted_start.run()

    def _transition_if_declared(self, event: BotLifecycleEvent) -> None:
        state = self._context.state
        if state.can(event):
            state.transition(event)
        else:
            logger.info(
                "Bot %s: %s ignored in %s", self.bot_id, event.value, state.state.value
            )

    def _price(self) -> Decimal:
        return self._context.reference_price.current()
