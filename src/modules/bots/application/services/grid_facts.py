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
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    bot_owner_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_interrupted_start import (
    GridInterruptedStart,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_key_probe import (
    GridKeyProbe,
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stopper import (
    GridStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stream_gap import (
    GridStreamGap,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_terms_watch import (
    GridTermsWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderEnd,
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_facts import IBotFacts
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
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

logger = logging.getLogger("App.Bots.GridExecutor")

_S = BotLifecycleState
_E = BotLifecycleEvent

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

    def on_fill(self, fill: BotOrderFill) -> None:
        self._post(f"fill of {fill.client_order_id}", lambda: self._apply_fill(fill))

    def on_end(self, end: BotOrderEnd) -> None:
        self._post(f"end of {end.client_order_id}", lambda: self._apply_end(end))

    def on_tick(self, tick: PriceTick) -> None:
        self._post("tick", lambda: self._parts.prices.on_tick(tick))

    def on_price_age_check(self) -> None:
        """The price watch's beat: is the feed quiet, and (`EPIC-035F`, on its
        own interval) does the exchange still accept the key."""
        self._post("price age check", self._parts.prices.check_age)
        self._post("key probe", self._parts.key_probe.check)
        self._post("terms refresh", self._parts.terms_watch.check)

    def on_switch(self, enabled: bool, cause: TradingSwitchCause) -> None:
        self._post("trading switch", lambda: self._apply_switch(enabled, cause))

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
        level_fill = self._level_fill(fill)
        if state.runtime.level_of(fill.client_order_id) is None:
            if fill.client_order_id in self._context.off_ladder:
                state.update(book_market_fill(state.runtime, fill.side, level_fill))
            else:
                logger.info(
                    "Bot %s: fill of %s ignored; no level holds it and the bot "
                    "neither sent it as a market order nor took it off the ladder",
                    self._context.state.bot_id,
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
        self._parts.placer.act(reaction.actions)

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

    def _apply_switch(self, enabled: bool, cause: TradingSwitchCause) -> None:
        state = self._context.state
        if not enabled:
            self._forget_proposal()
            if state.state in (_S.STARTING, _S.RUNNING, _S.PAUSED):
                state.transition(
                    _E.SWITCH_OFF, GridReason.SWITCH_OFF, _SWITCH_OFF_DETAIL[cause]
                )
            return
        if state.state in (_S.DRAFT, _S.STOPPED):
            return
        self._reclaim_lease()
        if state.state is _S.RECOVERING:
            self._parts.reconciler.run()
            # Read through the context again: run() moves the state, and a
            # type checker keeps `state.state` narrowed to RECOVERING.
            if self._context.state.state is _S.RUNNING:
                self._parts.placer.release_held()
        elif state.state is _S.STOPPING:
            self._parts.stop.after_switch_on()
        elif state.state is _S.HALTED:
            self._parts.interrupted_start.run()

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
