"""`EPIC-029E` — what one Grid bot does about each fact it is told.

Split from `GridExecutor` (commands) by the port split: the facts — a fill, an
end, a tick, the trading switch, the user-data stream — have their own callers
(`IBotFacts`). Every fact is **posted** onto the bot's one queue through the
executor's guarded `post`, so the ladder keeps one writer and a fact never
interleaves with an order in flight; the bodies below run on that worker.

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
from dataclasses import dataclass
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_blocked_counter import (
    GridBlockedCounter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budget import (
    bot_owner_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_exit_report import (
    GridExitReport,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_fill_announcer import (
    GridFillAnnouncer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_fill_conversion import (
    GridFillConversion,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_ladder_placer import (
    GridLadderPlacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_halt_recovery import (
    GridHaltRecovery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_reconciler import (
    GridReconciler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.start.grid_interrupted_start import (
    GridInterruptedStart,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_mark_exit import (
    GridMarkExit,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stopper import (
    GridStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_key_probe import (
    GridKeyProbe,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_price_reaction import (
    GridPriceReaction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_risk_watch import (
    GridRiskWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_stream_gap import (
    GridStreamGap,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_terms_watch import (
    GridTermsWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotFundingCharge,
    BotOrderEnd,
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_facts import IBotFacts
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_protection import (
    IExposureProtection,
    ProtectionVerdict,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_books import (
    book_exit_fill,
    book_market_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LadderRules,
    LevelEnd,
    drop_order,
    on_end,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergence,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_opener import (
    OpenedByPerson,
    SessionOpener,
)

logger = logging.getLogger("App.Bots.GridExecutor")

_S = BotLifecycleState
_E = BotLifecycleEvent

#: The states an Emergency Stop or a switch-off moves to HALTED (`switch_off` is declared in
#: each). A bot waiting in AWAITING_RECOVERY is one: trading off ends the wait before any
#: automatic attempt (ADR 042 §2.4); so is a bot waiting for its range, which must not survive an
#: Emergency Stop and open its whole capital on the next in-range price (`EPIC-044`, ADR 044 D8).
_SWITCHED_OFF_FROM: frozenset[BotLifecycleState] = frozenset(
    {_S.STARTING, _S.RUNNING, _S.PAUSED, _S.AWAITING_RECOVERY, _S.AWAITING_RANGE}
)

_SWITCH_OFF_DETAIL = {
    TradingSwitchCause.EMERGENCY_STOP: (
        "Emergency Stop cancelled every order and sold what was bought since "
        "the session opened"
    ),
}


@dataclass(frozen=True, slots=True)
class GridFactParts:
    """The executor's collaborators the facts act through (shared, not copied:
    the gap's unconfirmed strike and the last price live in them)."""

    placer: GridLadderPlacer
    prices: GridPriceReaction
    gap: GridStreamGap
    stop: GridStopper
    reconciler: GridReconciler
    interrupted_start: GridInterruptedStart
    key_probe: GridKeyProbe
    terms_watch: GridTermsWatch
    #: The ladder's reaction to a fill, asking the exchange before a counter halts (`BUG-225`).
    counters: GridBlockedCounter
    #: Tells the app an order filled whole (`BOT-189`).
    fills: GridFillAnnouncer
    #: A position venue's liquidation and divergence watch (`EPIC-039F`); `None` on Spot,
    #: which has neither.
    risk_watch: GridRiskWatch | None = None
    #: A position venue's stop loss and take profit on the mark price; `None` on Spot.
    mark_exit: GridMarkExit | None = None
    #: A position venue's exchange-side protective stop (`EPIC-039L`); `None` on Spot.
    protection: IExposureProtection | None = None
    #: The recovery run of a bot waiting in AWAITING_RECOVERY (`EPIC-042C`).
    halt_recovery: GridHaltRecovery | None = None


class GridFacts(IBotFacts):
    """Posts each fact onto the bot's queue and applies it on the worker."""

    def __init__(
        self,
        context: GridRunContext,
        parts: GridFactParts,
        post: Callable[[str, Callable[[], None]], None],
        forget_proposal: Callable[[], None],
    ) -> None:
        self._context = context
        self._parts = parts
        self._post = post
        self._forget_proposal = forget_proposal
        self._conversion = GridFillConversion(context)
        self._exit_report = GridExitReport(context)

    def on_fill(self, fill: BotOrderFill) -> None:
        # A fill changes the account's position: the venue's shared reading of it is dropped here,
        # on the stream's thread, before any watch of the venue can look at it (`BOT-184`).
        self._context.gateway.account_reads.account_changed()
        self._post(f"fill of {fill.client_order_id}", lambda: self._apply_fill(fill))

    def on_end(self, end: BotOrderEnd) -> None:
        self._post(f"end of {end.client_order_id}", lambda: self._apply_end(end))

    def on_funding(self, charge: BotFundingCharge) -> None:
        self._post("funding", lambda: self._apply_funding(charge))

    def on_tick(self, tick: PriceTick) -> None:
        self._post("tick", lambda: self._parts.prices.on_tick(tick))

    def on_price_age_check(self) -> None:
        """The price watch's beat: is the feed quiet, and (`EPIC-035F`, on its
        own interval) does the exchange still accept the key."""
        self._post("price age check", self._parts.prices.check_age)
        if self._parts.halt_recovery is not None:
            self._post("halt recovery check", self._parts.halt_recovery.check)
        self._post("key probe", self._parts.key_probe.check)
        self._post("terms refresh", self._parts.terms_watch.check)
        if self._parts.mark_exit is not None:
            self._post("mark exit check", self._parts.mark_exit.check)
        if self._parts.risk_watch is not None:
            self._post("risk check", self._parts.risk_watch.check)
        if self._parts.protection is not None:
            self._post("protective stop check", self._supervise_protection)

    def on_position_divergence(self, divergence: PositionDivergence) -> None:
        watch = self._parts.risk_watch
        if watch is not None:
            self._post("position divergence", lambda: watch.on_divergence(divergence))

    def on_switch(
        self,
        enabled: bool,
        cause: TradingSwitchCause,
        opened_for: SessionOpener = None,
    ) -> None:
        self._post(
            "trading switch", lambda: self._apply_switch(enabled, cause, opened_for)
        )

    def reconcile_after_gap(self) -> None:
        self._post("reconcile after a stream gap", self._parts.gap.reconcile)

    def halt_user_stream_down(self, down_for: timedelta) -> None:
        self._post("halt, stream down", lambda: self._parts.gap.halt(down_for))

    # --- on the worker ---

    def _apply_fill(self, fill: BotOrderFill) -> None:
        state = self._context.state
        applied = self._context.applied_fills
        if applied.knows(fill.client_order_id, fill.trade_id):
            logger.info(
                "Bot %s: fill %s of %s ignored; it was already counted [duplicate-fill]",
                state.bot_id,
                fill.trade_id,
                fill.client_order_id,
            )
            return
        applied.record(fill.client_order_id, fill.trade_id)
        level_fill = self._conversion.level_fill(fill)
        if state.runtime.level_of(fill.client_order_id) is None:
            if fill.client_order_id in self._context.off_ladder:
                booked = (
                    book_exit_fill
                    if self._context.off_ladder.is_exit(fill.client_order_id)
                    else book_market_fill
                )
                state.update(
                    booked(state.runtime, fill.side, level_fill).with_fill_commission(
                        level_fill.base_fee, level_fill.quote_fee, level_fill.price
                    )
                )
                if self._is_protective_stop(fill.client_order_id):
                    # The exchange ran the stop that stands over the position: the look at
                    # the stops reads its status and the bot stops (`EPIC-039L`).
                    self._supervise_protection()
                if self._context.off_ladder.is_exit(fill.client_order_id):
                    self._exit_report.after_exit_fill()
            else:
                logger.info(
                    "Bot %s: fill of %s ignored; no level holds it and the bot "
                    "neither sent it as a market order nor took it off the ladder",
                    self._context.state.bot_id,
                    fill.client_order_id,
                )
            return
        reaction = self._parts.counters.on_fill(level_fill)
        state.update(
            reaction.runtime.with_fill_commission(
                level_fill.base_fee, level_fill.quote_fee, level_fill.price
            )
        )
        self._parts.fills.announce(reaction.filled)
        self._parts.placer.act(reaction.actions)

    def _apply_funding(self, charge: BotFundingCharge) -> None:
        """`EPIC-039G` — only a bot that has run holds a position to be charged on."""
        state = self._context.state
        if state.state in (_S.DRAFT, _S.STOPPED):
            return
        state.update(state.runtime.with_funding(charge.amount))
        logger.debug("Bot %s: funding %s booked", state.bot_id, charge.amount)

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
        self._parts.placer.act(reaction.actions)

    def _apply_switch(
        self, enabled: bool, cause: TradingSwitchCause, opened_for: SessionOpener
    ) -> None:
        state = self._context.state
        if not enabled:
            self._forget_proposal()
            if state.state in _SWITCHED_OFF_FROM:
                state.transition(
                    _E.SWITCH_OFF, GridReason.SWITCH_OFF, _SWITCH_OFF_DETAIL[cause]
                )
            return
        if state.state in (_S.DRAFT, _S.STOPPED):
            return
        self._reclaim_lease()
        if state.state is _S.RECOVERING:
            if opened_for is None or opened_for == state.bot_id:
                self.reconcile_recovering()
            else:
                # `BOT-183`, `BOT-197` (ADR 038 O2): a restart's RECOVERING bot goes back to work
                # on its own Resume, never because another bot's command or a person's manual
                # order or strategy arm opened the venue's session.
                logger.info(
                    "Bot %s: the order session was opened for %s; waiting for its own "
                    "resume [recovering-waits]",
                    state.bot_id,
                    opened_for.value
                    if isinstance(opened_for, OpenedByPerson)
                    else f"bot {opened_for}",
                )
        elif state.state is _S.STOPPING:
            self._parts.stop.after_switch_on()
        elif state.state is _S.HALTED:
            self._parts.interrupted_start.run()

    def reconcile_recovering(self) -> None:
        """Bring a RECOVERING bot level with the exchange and, if it is back to
        RUNNING, lay what was held. Runs on the worker: the switch-on event and
        the owner's Resume (`BUG-204`) both end here, so one reconcile serves both."""
        # The stops first (`EPIC-039L`, decision D7): one that ran while the app was closed
        # has left the account flat, which the reconcile would call a mismatch. This look only
        # reads; a missing stop is put back once the reconcile has registered the budget.
        self._supervise_protection()
        if self._state() is not _S.RECOVERING:
            return
        self._parts.reconciler.run()
        # The reconcile moves the state, and has registered the budget: a stop that is missing is
        # put back now, before anything held is laid.
        if self._state() in (_S.RUNNING, _S.PAUSED):
            self._supervise_protection()
        if self._state() is _S.RUNNING:
            self._parts.placer.release_held()

    def _state(self) -> BotLifecycleState:
        """The bot's state now: read through here so a type checker does not keep the one it
        narrowed to before a step that moves it."""
        return self._context.state.state

    def _is_protective_stop(self, client_order_id: str) -> bool:
        return any(
            stop.client_order_id == client_order_id
            for stop in self._context.state.runtime.protective_stops
        )

    def _supervise_protection(self) -> None:
        """Look at the protective stop; one that ran closed the position, so the bot stops."""
        protection = self._parts.protection
        if protection is None:
            return
        if protection.supervise() is ProtectionVerdict.TRIGGERED:
            self._parts.stop.run(
                ExposureHandling.CLOSE_AT_MARKET,
                GridReason.PROTECTIVE_STOP_TRIGGERED,
                "the stop standing on the exchange closed the position",
            )

    def _reclaim_lease(self) -> None:
        """Leases live in memory: a restored bot takes its symbol back when
        trading is enabled (ADR D12), so a manual order on it is refused again."""
        symbol = self._context.state.bot.definition.symbol
        if not self._context.session.claim_symbol(
            symbol, bot_owner_id(self._context.state.bot_id)
        ):
            logger.info(
                "Bot %s: %s is held by another owner",
                self._context.state.bot_id,
                symbol,
            )
