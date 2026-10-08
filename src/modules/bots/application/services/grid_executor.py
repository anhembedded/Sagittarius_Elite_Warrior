"""`EPIC-029E` — the actor that runs one Grid bot (ADR D9–D11, §3.1).

Every entry point **posts** to the bot's queue and returns: the commands from
the use cases (start, pause, resume, stop) and the facts from the handlers
(fills, ends, ticks, the switch). Only the queue's worker touches the bot's
record, submits, cancels and writes the store, so the ladder has one writer
and an event never interleaves with an order in flight.

  · **A fill** goes through `on_fill` when a level holds the order (the counter
    order follows, held while PAUSED), or `book_market_fill` when it is one of
    the bot's market orders (the opening buy, an exit slice).
  · **An end** re-places the order once while RUNNING (held while PAUSED); in
    any other state the level just empties — the bot's own cancels end orders
    too.
  · **A tick** remembers the price; at or beyond the stop loss or the take
    profit it runs Stop with *sell base* forced, recording why (D11).
  · **Trading off** (`switch_off`) halts a running bot without another order;
    a stop in progress waits, and runs again when trading comes back.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    bot_owner_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_housekeeping import (
    GridHousekeeping,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_interrupted_start import (
    GridInterruptedStart,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_ladder_placer import (
    GridLadderPlacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_price_reaction import (
    GridPriceReaction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_reconciler import (
    GridReconciler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_recovery_reader import (
    GridRecoveryReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_resume_sequence import (
    GridResumeSequence,
    ResumeProposal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_start_sequence import (
    GridStartSequence,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stopper import (
    GridStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stream_gap import (
    GridStreamGap,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_task_guard import (
    GridTaskGuard,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.symbol_status_gate import (
    SymbolStatusGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderEnd,
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
    IBotExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import plan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LadderRules,
    LevelEnd,
    LevelFill,
    book_market_fill,
    drop_order,
    on_end,
    on_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
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
    ) -> None:
        self._context = context
        self._queue = queue
        self._start = GridStartSequence(context)
        self._stop = GridStopper(context, retries, self._post, self._price)
        self._status = SymbolStatusGate(context)
        self._resume = GridResumeSequence(context, self._start, self._status)
        self._reconciler = GridReconciler(context)
        self._placer = GridLadderPlacer(context)
        self._recovery = GridRecoveryReader(context)
        self._interrupted_start = GridInterruptedStart(context)
        self._gap = GridStreamGap(
            context, self._reconciler, self._placer.release_held, self._post
        )
        self._guard = GridTaskGuard(context, GridHousekeeping(context))
        self._prices = GridPriceReaction(context, self._stop)
        self._proposal: ResumeProposal | None = None

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

    def close(self) -> None:
        """Run what is queued, then stop the worker."""
        self._queue.close()

    # --- commands (IBotExecutor) ---

    def start(self) -> None:
        self._post("start", self._run_start)

    def pause(self) -> None:
        self._post("pause", self._run_pause)

    def resume(self) -> None:
        self._post("resume", self._run_resume)

    def stop(self, base: BaseHandling) -> None:
        self._post("stop", lambda: self._stop.run(base, GridReason.USER_STOP))

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

    # --- facts, copied off the caller's thread ---

    def on_fill(self, fill: BotOrderFill) -> None:
        self._post(f"fill of {fill.client_order_id}", lambda: self._apply_fill(fill))

    def on_end(self, end: BotOrderEnd) -> None:
        self._post(f"end of {end.client_order_id}", lambda: self._apply_end(end))

    def on_tick(self, price: Decimal) -> None:
        self._post("tick", lambda: self._prices.on_tick(price))

    def on_price_age_check(self) -> None:
        self._post("price age check", self._prices.check_age)

    def on_switch(self, enabled: bool, cause: TradingSwitchCause) -> None:
        self._post("trading switch", lambda: self._apply_switch(enabled, cause))

    def reconcile_after_gap(self) -> None:
        self._post("reconcile after a stream gap", self._gap.reconcile)

    def halt_user_stream_down(self, down_for: timedelta) -> None:
        self._post("halt, stream down", lambda: self._gap.halt(down_for))

    # --- every task through the guard ---

    def _post(self, what: str, task: Callable[[], None]) -> None:
        self._queue.post(lambda: self._guard.run(what, task))

    # --- on the worker ---

    def _run_start(self) -> None:
        state = self._context.state
        if state.state is not _S.STARTING:
            logger.info("Bot %s: start ignored in %s", self.bot_id, state.state.value)
            return
        if not self._status.admits():
            return
        price = self._price()
        self._start.run(plan(self._context.params, self._context.terms, price))

    def _run_pause(self) -> None:
        self._transition_if_declared(_E.PAUSE)

    def _run_resume(self) -> None:
        state = self._context.state
        if state.state is _S.HALTED:
            self._proposal = self._resume.propose(self._price())
            return
        if state.state is not _S.PAUSED:
            logger.info("Bot %s: resume ignored in %s", self.bot_id, state.state.value)
            return
        if not self._status.admits():
            return
        state.transition(_E.RESUME)
        self._placer.release_held()

    def _run_confirm(self) -> None:
        proposal, self._proposal = self._proposal, None
        if self._context.state.state is not _S.HALTED or proposal is None:
            logger.info(
                "Bot %s: nothing to confirm in %s",
                self.bot_id,
                self._context.state.state.value,
            )
            return
        self._resume.confirm(proposal)

    def _recover(self) -> None:
        self._recovery.report()
        self._interrupted_start.run()

    def _apply_fill(self, fill: BotOrderFill) -> None:
        state = self._context.state
        level_fill = self._level_fill(fill)
        if state.runtime.level_of(fill.client_order_id) is None:
            if fill.client_order_id in self._context.off_ladder:
                state.update(book_market_fill(state.runtime, fill.side, level_fill))
            else:
                logger.info(
                    "Bot %s: fill of %s ignored; no level holds it and the bot "
                    "neither sent it as a market order nor took it off the ladder",
                    self.bot_id,
                    fill.client_order_id,
                )
            return
        reaction = on_fill(
            state.runtime,
            level_fill,
            self._context.terms.step_size,
            hold=state.state is not _S.RUNNING,
        )
        state.update(reaction.runtime)
        self._placer.act(reaction.actions)

    def _apply_end(self, end: BotOrderEnd) -> None:
        state = self._context.state
        if state.state not in (_S.RUNNING, _S.PAUSED):
            state.update(drop_order(state.runtime, end.client_order_id))
            self._context.off_ladder.add(end.client_order_id)
            return
        terms = self._context.terms
        reaction = on_end(
            state.runtime,
            LevelEnd(end.client_order_id, state.now(), end.rejection),
            LadderRules(terms.step_size, terms.min_notional),
            hold=state.state is _S.PAUSED,
        )
        state.update(reaction.runtime)
        self._placer.act(reaction.actions)

    def _apply_switch(self, enabled: bool, cause: TradingSwitchCause) -> None:
        state = self._context.state
        if not enabled:
            self._proposal = None
            if state.state in (_S.STARTING, _S.RUNNING, _S.PAUSED):
                state.transition(
                    _E.SWITCH_OFF, GridReason.SWITCH_OFF, _SWITCH_OFF_DETAIL[cause]
                )
            return
        if state.state in (_S.DRAFT, _S.STOPPED):
            return
        self._reclaim_lease()
        if state.state is _S.RECOVERING:
            self._reconciler.run()
            # Read through the context again: run() moves the state, and a
            # type checker keeps `state.state` narrowed to RECOVERING.
            if self._context.state.state is _S.RUNNING:
                self._placer.release_held()
        elif state.state is _S.STOPPING:
            self._stop.after_switch_on()
        elif state.state is _S.HALTED:
            self._interrupted_start.run()

    def _reclaim_lease(self) -> None:
        """Leases live in memory: a restored bot takes its symbol back when
        trading is enabled (ADR D12), so a manual order on it is refused again."""
        symbol = self.symbol
        if not self._context.session.claim_symbol(symbol, bot_owner_id(self.bot_id)):
            logger.info("Bot %s: %s is held by another owner", self.bot_id, symbol)

    def _transition_if_declared(self, event: BotLifecycleEvent) -> None:
        state = self._context.state
        if state.can(event):
            state.transition(event)
        else:
            logger.info(
                "Bot %s: %s ignored in %s", self.bot_id, event.value, state.state.value
            )

    def _level_fill(self, fill: BotOrderFill) -> LevelFill:
        base_asset = self._context.base_asset
        fee = fill.fee_amount or Decimal(0)
        return LevelFill(
            fill.client_order_id,
            fill.price,
            fill.quantity,
            base_fee=fee if fill.fee_asset == base_asset else Decimal(0),
            quote_fee=fee if fill.fee_asset == BUDGET_QUOTE_ASSET else Decimal(0),
        )

    def _price(self) -> Decimal:
        return self._prices.last_price or self._context.gateway.market_price()
