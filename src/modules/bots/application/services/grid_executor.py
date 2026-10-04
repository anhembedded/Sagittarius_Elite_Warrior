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
from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    fail_with,
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_start_sequence import (
    GridStartSequence,
    log_order,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stop_sequence import (
    GridStopSequence,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderEnd,
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
    IBotExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    crossed_exit,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import plan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    GridAction,
    Halt,
    LevelFill,
    PlaceOrder,
    accepted,
    book_market_fill,
    drop_order,
    on_end,
    on_fill,
    placed,
    release_held,
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
    TradingSwitchCause.DISABLED: (
        "trading was disabled; the bot's resting orders are still on the exchange"
    ),
    TradingSwitchCause.EMERGENCY_STOP: (
        "Emergency Stop cancelled every order and sold what was bought since "
        "the last enable"
    ),
}


class GridExecutor(IBotExecutor):
    """One Grid bot's actor: every call is queued and run in order."""

    def __init__(self, context: GridRunContext, queue: IBotWorkQueue) -> None:
        self._context = context
        self._queue = queue
        self._start = GridStartSequence(context)
        self._stop = GridStopSequence(context)
        self._last_price: Decimal | None = None

    @property
    def bot_id(self) -> str:
        return self._context.state.bot_id

    @property
    def venue(self) -> TradingVenue:
        return self._context.state.bot.definition.venue

    @property
    def symbol(self) -> str:
        return self._context.state.bot.definition.symbol

    # --- commands (IBotExecutor) ---

    def start(self) -> None:
        self._queue.post(self._run_start)

    def pause(self) -> None:
        self._queue.post(self._run_pause)

    def resume(self) -> None:
        self._queue.post(self._run_resume)

    def stop(self, base: BaseHandling) -> None:
        self._queue.post(lambda: self._run_stop(base, GridReason.USER_STOP))

    # --- facts, copied off the caller's thread ---

    def on_fill(self, fill: BotOrderFill) -> None:
        self._queue.post(lambda: self._apply_fill(fill))

    def on_end(self, end: BotOrderEnd) -> None:
        self._queue.post(lambda: self._apply_end(end))

    def on_tick(self, price: Decimal) -> None:
        self._queue.post(lambda: self._apply_tick(price))

    def on_switch(self, enabled: bool, cause: TradingSwitchCause) -> None:
        self._queue.post(lambda: self._apply_switch(enabled, cause))

    # --- on the worker ---

    def _run_start(self) -> None:
        state = self._context.state
        if state.state is not _S.STARTING:
            logger.info("Bot %s: start ignored in %s", self.bot_id, state.state.value)
            return
        price = self._price()
        self._start.run(plan(self._context.params, self._context.terms, price))

    def _run_pause(self) -> None:
        self._transition_if_declared(_E.PAUSE)

    def _run_resume(self) -> None:
        state = self._context.state
        if state.state is not _S.PAUSED:
            logger.info("Bot %s: resume ignored in %s", self.bot_id, state.state.value)
            return
        state.transition(_E.RESUME)
        reaction = release_held(state.runtime)
        state.update(reaction.runtime)
        self._act(reaction.actions)

    def _run_stop(
        self, base: BaseHandling, reason: GridReason, detail: str = ""
    ) -> None:
        state = self._context.state
        sell = base is BaseHandling.SELL_AT_MARKET
        if state.can(_E.STOP):
            state.transition(_E.STOP, reason, detail or reason.value)
        elif state.state is not _S.STOPPING:
            logger.info("Bot %s: stop ignored in %s", self.bot_id, state.state.value)
            return
        state.update(replace(state.runtime, sell_base_on_stop=sell))
        self._stop.run(base, self._price())

    def _apply_fill(self, fill: BotOrderFill) -> None:
        state = self._context.state
        level_fill = self._level_fill(fill)
        if state.runtime.level_of(fill.client_order_id) is None:
            state.update(book_market_fill(state.runtime, fill.side, level_fill))
            return
        reaction = on_fill(
            state.runtime,
            level_fill,
            self._context.terms.step_size,
            hold=state.state is not _S.RUNNING,
        )
        state.update(reaction.runtime)
        self._act(reaction.actions)

    def _apply_end(self, end: BotOrderEnd) -> None:
        state = self._context.state
        if state.state not in (_S.RUNNING, _S.PAUSED):
            state.update(drop_order(state.runtime, end.client_order_id))
            return
        reaction = on_end(
            state.runtime,
            end.client_order_id,
            state.now(),
            end.rejection,
            hold=state.state is _S.PAUSED,
        )
        state.update(reaction.runtime)
        self._act(reaction.actions)

    def _apply_tick(self, price: Decimal) -> None:
        self._last_price = price
        if self._context.state.state not in (_S.RUNNING, _S.PAUSED):
            return
        params = self._context.params
        reason = crossed_exit(price, params.stop_loss_price, params.take_profit_price)
        if reason is not None:
            self._run_stop(BaseHandling.SELL_AT_MARKET, reason, f"price {price}")

    def _apply_switch(self, enabled: bool, cause: TradingSwitchCause) -> None:
        state = self._context.state
        if enabled:
            if state.state is _S.STOPPING:
                base = (
                    BaseHandling.SELL_AT_MARKET
                    if state.runtime.sell_base_on_stop
                    else BaseHandling.KEEP
                )
                self._stop.run(base, self._price())
            return
        if state.state in (_S.STARTING, _S.RUNNING, _S.PAUSED):
            state.transition(
                _E.SWITCH_OFF, GridReason.SWITCH_OFF, _SWITCH_OFF_DETAIL[cause]
            )

    def _act(self, actions: tuple[GridAction, ...]) -> None:
        for action in actions:
            if isinstance(action, Halt):
                halt_with(self._context.state, action.reason, action.detail)
                return
            if not self._place(action):
                return

    def _place(self, action: PlaceOrder) -> bool:
        state = self._context.state
        outcome = self._context.gateway.place_limit(
            action.side, action.price, action.quantity
        )
        log_order(state.bot_id, action, outcome.client_order_id or outcome.detail)
        if not outcome.done:
            fail_with(state, outcome, f"L{action.level_index} {action.side.value}")
            return False
        oid = outcome.client_order_id
        state.update(accepted(placed(state.runtime, action, oid), oid))
        return True

    def _transition_if_declared(self, event: BotLifecycleEvent) -> None:
        state = self._context.state
        if state.can(event):
            state.transition(event)
        else:
            logger.info(
                "Bot %s: %s ignored in %s", self.bot_id, event.value, state.state.value
            )

    def _level_fill(self, fill: BotOrderFill) -> LevelFill:
        base_asset = self._context.state.bot.definition.symbol.removesuffix(
            BUDGET_QUOTE_ASSET
        )
        fee = fill.fee_amount or Decimal(0)
        return LevelFill(
            fill.client_order_id,
            fill.price,
            fill.quantity,
            base_fee=fee if fill.fee_asset == base_asset else Decimal(0),
            quote_fee=fee if fill.fee_asset == BUDGET_QUOTE_ASSET else Decimal(0),
        )

    def _price(self) -> Decimal:
        return self._last_price or self._context.gateway.market_price()
