"""`EPIC-044B` — a Grid waiting for its range enters it and lays its ladder (ADR 044 D4, D5).

`EPIC-046A` adds the optional trigger price to the same wait (ADR 046 D2): the gate is the range
and then the trigger (`entry_gate`), so a LONG bot with a trigger waits inside its range until the
price is at or below it, a SHORT one until it is at or above it. The state, the confirmation by
the fresh book and the pre-checks below are unchanged; only "inside the range" became "the gate
is open".

A bot started away from its range sits in AWAITING_RANGE with nothing placed. Every price the
exits are judged on arrives here (`GridPriceReaction`: the streamed last price on Spot, the mark
price on a position venue), and when one is inside the range (`range_position`, the bounds
included) the bot decides whether to enter. **The decision is made in AWAITING_RANGE, before any
transition**, so a price that flickers across a bound writes no journal row and no log line per
beat:

  1. the trigger is confirmed by the book price read fresh (`GridReferencePrice.fresh`, never
     the held tick), at most once per `ENTRY_READ_EVERY_SECONDS`;
  2. the pre-checks run on that price: the symbol trades, the owner budget registers again, and
     the ladder the plan would lay clears the exchange minimum and trading's per-order cap;
  3. only then `range_entered` takes the bot to STARTING and the start sequence lays the ladder,
     exactly as a normal start at that price would, opening trade included.

A refusal of the plan (a refused budget, an order under the minimum or over the cap, a delisted
symbol) halts the bot with `ENTRY_REFUSED` or the cause's own reason; a transient cause (trading
off, the symbol not in TRADING, a rate limit, a price that cannot be read) keeps it waiting and is
told once per episode. What the start sequence meets after `range_entered` follows STARTING's rows
(ADR 044 D5). Touched only on the bot's worker.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_housekeeping import (
    GridHousekeeping,
    refusal_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_order_failure import (
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stop_request import (
    stop_asked,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.symbol_status_gate import (
    SymbolStatusGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_range_entered_event import (
    BotRangeEnteredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    FreshPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_entry_gate import (
    EntryGate,
    entry_gate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_order_sizing import (
    find_breach,
    find_cap_breach,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: The most often the book is read to confirm an in-range trigger: Spot's trigger is every
#: kline update, a position venue's every beat of the price watch (ADR 044 D4).
ENTRY_READ_EVERY_SECONDS: float = 5.0

#: How long a deferred entry waits before it asks again (the readiness reads the account).
ENTRY_RETRY_AFTER_DEFERRAL: float = 30.0

#: Budget refusals that are the state of the world, not of the plan: they pass by themselves.
_TRANSIENT_REFUSALS: frozenset[OwnerBudgetRefusal] = frozenset(
    {OwnerBudgetRefusal.TRADING_SWITCH_OFF, OwnerBudgetRefusal.INVENTORY_UNAVAILABLE}
)

_S = BotLifecycleState


class GridRangeEntry:
    """Decides, for a bot in AWAITING_RANGE, whether the price now lets it lay its ladder."""

    def __init__(
        self,
        context: GridRunContext,
        status: SymbolStatusGate,
        housekeeping: GridHousekeeping,
        lay: Callable[[GridPlan], None],
    ) -> None:
        """@param lay Runs the start sequence for a plan (`GridStartSequence.run`)."""
        self._context = context
        self._status = status
        self._housekeeping = housekeeping
        self._lay = lay
        #: The monotonic moment before which no new attempt is made.
        self._not_before: float | None = None
        self._deferred_for: str | None = None

    def waits_for_the_range(self, price: Decimal) -> bool:
        """Start with the price outside the range, or short of the trigger: place nothing and
        wait (ADR 044 D1, ADR 046 D1).

        Answers whether the bot now waits; `False` leaves a bot whose gate is open for the start
        sequence."""
        gate = entry_gate(self._context.params, price)
        if gate is EntryGate.OPEN:
            return False
        logger.info(
            "Bot %s: %s; nothing is placed, waiting [range-wait]",
            self._context.state.bot_id,
            self._why_closed(gate, price),
        )
        self._context.state.transition(BotLifecycleEvent.PRICE_OUTSIDE_RANGE)
        return True

    def on_price(self, price: Decimal) -> None:
        """A price the exits are judged on arrived. Does nothing outside AWAITING_RANGE."""
        state = self._context.state
        if state.state is not _S.AWAITING_RANGE:
            self._forget()
            return
        if entry_gate(self._context.params, price) is not EntryGate.OPEN:
            self._forget()
            return
        now = self._context.monotonic.seconds()
        if self._not_before is not None and now < self._not_before:
            return
        self._not_before = now + ENTRY_READ_EVERY_SECONDS
        self._attempt(price)

    def _attempt(self, trigger: Decimal) -> None:
        fresh = self._fresh_price()
        if fresh is None:
            return
        gate = entry_gate(self._context.params, fresh)
        if gate is not EntryGate.OPEN:
            self._defer(
                f"{self._why_closed(gate, fresh)} although the price {trigger} that "
                "arrived opened it"
            )
            return
        if not self._symbol_trades():
            return
        if not self._budget_registers():
            return
        ladder = plan(
            self._context.params, self._context.terms, fresh, self._context.level_sizing
        )
        if self._refused_by_sizing(ladder) or not self._ready_to_lay():
            return
        if stop_asked(self._context):
            return
        self._enter(fresh, trigger, ladder)

    def _why_closed(self, gate: EntryGate, price: Decimal) -> str:
        """The words of a closed gate, one sentence for the log: the range, or the trigger."""
        params = self._context.params
        if gate is EntryGate.OUTSIDE_RANGE:
            return f"price {price} is outside the range {params.lower}-{params.upper}"
        side = (
            "at or above" if params.direction is TradeDirection.SHORT else "at or below"
        )
        return f"price {price} has not reached the trigger, which wants it {side} {params.trigger_price}"

    def _ready_to_lay(self) -> bool:
        """The balance and the plan's verdicts at this price, in the words of the Bots screen."""
        judged = self._context.entry_readiness.judge(self._context.state.bot)
        if judged.ready:
            return True
        if judged.transient:
            self._defer(f"the plan could not be judged: {judged.refusal}")
        else:
            self._refuse(judged.refusal)
        return False

    def _fresh_price(self) -> Decimal | None:
        try:
            return self._context.reference_price.fresh()
        except FreshPriceUnavailableError as unavailable:
            self._defer(f"the book price could not be read: {unavailable}")
        except ExchangeRateLimitedError as limited:
            self._limited(limited)
        return None

    def _symbol_trades(self) -> bool:
        status = self._status.read()
        if status.delisted:
            halt_with(self._context.state, GridReason.SYMBOL_DELISTED, status.detail)
            return False
        if not status.trades:
            self._defer(status.detail)
        return status.trades

    def _budget_registers(self) -> bool:
        try:
            registration = self._housekeeping.register()
        except ExchangeRateLimitedError as limited:
            self._limited(limited)
            return False
        if registration.registered:
            return not self._holds_something(registration)
        text = refusal_text(registration)
        if registration.refusal in _TRANSIENT_REFUSALS:
            self._defer(f"the owner budget was not registered: {text}")
        else:
            self._refuse(f"the owner budget was refused: {text}")
        return False

    def _holds_something(self, registration: OwnerBudgetRegistrationResult) -> bool:
        """A bot that waits holds nothing (ADR 044 D1). One that does - an order filled while it
        was resumed into the wait - is halted, not given a second ladder on top of what it holds,
        and the Resume that follows sizes its ladder to it."""
        held = registration.position or registration.inventory
        if held is None or held.quantity == 0:
            return False
        detail = (
            f"the bot holds {held.quantity} {self._context.base_asset} although it waited for "
            "its range; nothing was laid, resume to plan a ladder over it"
        )
        logger.warning(
            "Bot %s: %s [range-entry-refused]", self._context.state.bot_id, detail
        )
        self._forget()
        halt_with(self._context.state, GridReason.ENTRY_REFUSED, detail)
        return True

    def _refused_by_sizing(self, ladder: GridPlan) -> bool:
        context = self._context
        breach = find_breach(context.params, ladder, context.terms)
        if breach is not None:
            self._refuse(breach.text(context.base_asset, BUDGET_QUOTE_ASSET))
            return True
        over_cap = find_cap_breach(ladder, context.terms)
        if over_cap is None:
            return False
        self._refuse(
            f"the {over_cap.label} order is worth {over_cap.notional:.2f} "
            f"{BUDGET_QUOTE_ASSET}, above trading's cap of "
            f"{context.terms.max_notional_per_order} per order"
        )
        return True

    def _enter(self, price: Decimal, trigger: Decimal, ladder: GridPlan) -> None:
        state = self._context.state
        self._forget()
        logger.info(
            "Bot %s: price %s entered the range %s-%s (trigger %s); laying %d orders "
            "[range-entry]",
            state.bot_id,
            price,
            self._context.params.lower,
            self._context.params.upper,
            trigger,
            len(ladder.order_levels),
        )
        state.transition(BotLifecycleEvent.RANGE_ENTERED)
        self._lay(ladder)
        self._tell_the_ladder_is_laid(price)

    def _tell_the_ladder_is_laid(self, price: Decimal) -> None:
        """The owner hears once that the wait ended in a running ladder; a start sequence that
        halted or stopped instead has its own alert (`BotRangeEnteredEvent`)."""
        state = self._context.state
        if state.state is not _S.RUNNING:
            return
        params = self._context.params
        self._context.events.publish(
            BotRangeEnteredEvent(
                state.bot_id,
                price,
                params.lower,
                params.upper,
                len(state.runtime.open_orders),
            )
        )

    def _refuse(self, detail: str) -> None:
        state = self._context.state
        logger.warning(
            "Bot %s: the price entered the range but the plan is refused, %s; the bot "
            "halts, nothing was placed [range-entry-refused]",
            state.bot_id,
            detail,
        )
        self._forget()
        state.transition(
            BotLifecycleEvent.ENTRY_REFUSED, GridReason.ENTRY_REFUSED, detail
        )

    def _limited(self, limited: ExchangeRateLimitedError) -> None:
        self._context.gateway.note_rate_limit(limited.retry_after)
        self._defer(
            f"the exchange asked for a pause of {limited.retry_after.total_seconds():.0f} s"
        )

    def _defer(self, cause: str) -> None:
        """Keep waiting; the cause is said once per episode, at INFO, and after that at DEBUG (at most one per `ENTRY_READ_EVERY_SECONDS`)."""
        level = logging.DEBUG if cause == self._deferred_for else logging.INFO
        self._deferred_for = cause
        self._not_before = (
            self._context.monotonic.seconds() + ENTRY_RETRY_AFTER_DEFERRAL
        )
        logger.log(
            level,
            "Bot %s: the price is inside the range but entry waits: %s [range-entry-deferred]",
            self._context.state.bot_id,
            cause,
        )

    def _forget(self) -> None:
        self._not_before = None
        self._deferred_for = None
