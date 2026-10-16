"""`EPIC-039L` — a Futures Grid's exchange-side protective stop: when it is placed, kept, replaced and cancelled.

@details The policy of decisions D4 to D8 of `DECISION_2026-10-16`. The bot's stop-loss price
becomes a `STOP_MARKET` that closes the whole position of the symbol on the mark price. For a
LONG grid it is a SELL under the range, for a SHORT grid a BUY over it; a NEUTRAL grid has both
(its stop loss under the range, its take profit over it, which is the exit it has above), but the one on the side with no position is placed only once the owner has recorded that the
exchange does nothing with it (check T3, `NEUTRAL_BOTH_SIDES_VERIFIED`), because a close-all
order that could open a position is the hazard of `EPIC-026K`.

  · **Place** (`protect`, and `supervise` for a stop that is missing): the record is saved
    first, then the order is sent; a refusal by name drops the record and halts the bot, which
    closes its position (it is never left bare); the order is never sent while the account
    holds no position, because it would stand over nothing.
  · **Keep** (`supervise`, on the price watch's beat and after a reconcile): a stop that was
    standing and is on no open list is judged by the position alone: flat means the exchange
    ran it (`TRIGGERED`, the verdict the bot stops on), a position standing means it is placed
    again. A stop on a symbol the second read shows flat is cancelled (an orphan would open a
    position).
  · **Cancel** (`release`): only once the bot's own exposure is closed, never before; a cancel
    that did not go through leaves the stop and the stop of the bot waits.

A look that cannot read the position, the mark or the history changes nothing and says so.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_order_failure import (
    fail_with,
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protective_stop_book import (
    ProtectiveStopBook,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_protective_stop_event import (
    BotProtectiveStopEvent,
    ProtectiveStopChange,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_protection import (
    IExposureProtection,
    ProtectionVerdict,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_mark_source import (
    IMarkSource,
    MarkReadError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop import (
    ProtectiveStop,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop_fsm_matrix import (
    ProtectiveStopEvent,
    ProtectiveStopState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

logger = logging.getLogger("App.Bots.GridExecutor")

#: Whether a close-all order on the side with no position is known to do nothing (check T3 of
#: `DECISION_2026-10-16`, on Futures testnet). `False` until the owner has recorded it: then a
#: NEUTRAL grid stands only the stop that covers its position. Flipping it is a reviewed change.
NEUTRAL_BOTH_SIDES_VERIFIED = False

#: The states in which the bot holds or lays orders, or is about to again (a restored bot, before
#: its reconcile), and so keeps its position protected.
_SUPERVISED = frozenset(
    {
        BotLifecycleState.RUNNING,
        BotLifecycleState.PAUSED,
        BotLifecycleState.RECOVERING,
    }
)


@dataclass(frozen=True, slots=True)
class _Wanted:
    """A stop the plan asks for: which side it closes and where it triggers."""

    side: OrderSide
    trigger_price: Decimal


class ProtectiveStopService(IExposureProtection):
    """The protective stop of one Futures Grid."""

    def __init__(self, context: GridRunContext, marks: IMarkSource) -> None:
        self._context = context
        self._marks = marks
        self._book = ProtectiveStopBook(context)

    def protect(self, plan: GridPlan) -> bool:
        wanted = self._wanted()
        if not wanted:
            logger.warning(
                "Bot %s: the plan has no stop loss, so no stop stands on the exchange and "
                "the position is unprotected if the app stops [protective-stop]",
                self._context.state.bot_id,
            )
            return True
        position = self._context.gateway.position()
        if position is None:
            self._fail("the position could not be read to place the protective stop")
            return False
        # An opening that left the account flat has nothing to protect yet: the first beat
        # that finds a position places the stop.
        return position == 0 or self._place_wanted(position, {})

    def supervise(self) -> ProtectionVerdict:
        state = self._context.state
        if state.state not in _SUPERVISED or not self._wanted():
            return ProtectionVerdict.OK
        position = self._context.gateway.position()
        if position is None:
            logger.warning(
                "Bot %s: the position could not be read, so the protective stop is not "
                "looked at this time [protective-stop]",
                state.bot_id,
            )
            return ProtectionVerdict.OK
        open_stops = self._open_stops()
        for stop in self._book.stops:
            if self._settle(stop, open_stops, position) is ProtectionVerdict.TRIGGERED:
                return ProtectionVerdict.TRIGGERED
        if state.state is BotLifecycleState.RECOVERING:
            # Read only: trading takes a tagged order only under the bot's registered budget,
            # which the reconcile registers. What is missing is placed once it has.
            return ProtectionVerdict.OK
        if position == 0:
            self._cancel_over_nothing()
        else:
            self._place_wanted(position, open_stops)
        return ProtectionVerdict.OK

    def release(self) -> bool:
        released = True
        for stop in self._book.stops:
            released = self._release(stop) and released
        return released

    # -- keeping ------------------------------------------------------------

    def _place_wanted(self, position: Decimal, open_stops: dict[str, Order]) -> bool:
        """Have a stop standing for each side that covers `position`, then take down any other
        stop of the bot's that stands; `False` when one could not stand, the bot has moved."""
        stood = all(
            self._place_if_missing(want, open_stops)
            for want in self._wanted()
            if self._covers(want.side, position)
        )
        if stood:
            self._cancel_untracked(open_stops)
        return stood

    def _cancel_untracked(self, open_stops: dict[str, Order]) -> None:
        """A protective stop of the bot's that no record names and that is not the plan's (an
        old stop, a differing trigger, the side no position covers): it stands only after the
        plan's own does (decision D7), and then it goes, because it would close the position at a
        price nobody chose or open one on the side that has none."""
        known = {stop.client_order_id for stop in self._book.stops}
        for client_order_id in open_stops:
            if client_order_id in known:
                continue
            outcome = self._context.gateway.cancel(client_order_id)
            logger.warning(
                "Bot %s: cancelled the protective stop %s that the plan does not ask for "
                "(%s) [protective-stop]",
                self._context.state.bot_id,
                client_order_id,
                outcome.kind.value,
            )

    def _settle(
        self, stop: ProtectiveStop, open_stops: dict[str, Order], position: Decimal
    ) -> ProtectionVerdict | None:
        """The record of `stop` against the open orders; `TRIGGERED` when it left the exchange
        and the position with it."""
        if stop.state is ProtectiveStopState.TRIGGERED:
            return ProtectionVerdict.TRIGGERED
        if stop.client_order_id in open_stops:
            if stop.state is ProtectiveStopState.INTENDED:
                self._book.apply(stop, ProtectiveStopEvent.ACCEPTED)
            return None
        return self._explain_absence(stop, position)

    def _explain_absence(
        self, stop: ProtectiveStop, position: Decimal
    ) -> ProtectionVerdict | None:
        """The stop is on no open list. The decision needs the position alone, not the
        history (which the trading side serves up to 15 s old, and which names a fill by an id
        the stream may not have linked, decision D4): a stop that was standing and an account that
        is flat means the exchange ran it; with a position standing it is placed again."""
        standing = stop.state is ProtectiveStopState.STANDING
        logger.info(
            "Bot %s: protective stop %s %s is on no open list and the position is %s "
            "[protective-stop]",
            self._context.state.bot_id,
            stop.client_order_id,
            stop.state.value,
            position,
        )
        if standing and position == 0:
            self._book.apply(stop, ProtectiveStopEvent.TRIGGERED)
            self._announce(
                ProtectiveStopChange.TRIGGERED,
                f"{stop.client_order_id} left the exchange and the position is flat",
            )
            return ProtectionVerdict.TRIGGERED
        if standing:
            self._book.apply(stop, ProtectiveStopEvent.MISSING_WITH_POSITION)
            self._announce(
                ProtectiveStopChange.MISSING,
                f"{stop.client_order_id} is on no open list while a position of "
                f"{position} stands; placing it again",
            )
        elif position == 0:
            self._book.apply(stop, ProtectiveStopEvent.REJECTED)
        return None

    def _place_if_missing(self, want: _Wanted, open_stops: dict[str, Order]) -> bool:
        """Have a stop standing for `want`; `False` when it could not, the bot has moved."""
        held = next((s for s in self._book.stops if s.side is want.side), None)
        if held is not None and held.state is ProtectiveStopState.STANDING:
            return True
        if held is None:
            adopted = self._adopt(want, open_stops)
            if adopted:
                return True
            held = self._book.intend(want.side, want.trigger_price)
        return self._send(held)

    def _adopt(self, want: _Wanted, open_stops: dict[str, Order]) -> bool:
        """A stop of the right side already stands but the record lost it (the app died after
        the order and before the save): it is taken back, never placed twice."""
        tick = self._context.terms.tick_size
        for order in open_stops.values():
            if (
                order.side is want.side
                and order.stop_price is not None
                and abs(order.stop_price - want.trigger_price) <= tick
                and order.client_order_id
                not in {s.client_order_id for s in self._book.stops}
            ):
                stop = ProtectiveStop(
                    order.client_order_id, order.side, order.stop_price
                )
                self._context.off_ladder.add_exit(stop.client_order_id)
                self._context.state.update(
                    self._context.state.runtime.with_stop(
                        stop.moved(ProtectiveStopEvent.ACCEPTED) or stop
                    )
                )
                logger.info(
                    "Bot %s: adopted the protective stop %s [protective-stop]",
                    self._context.state.bot_id,
                    stop.client_order_id,
                )
                return True
        return False

    def _send(self, stop: ProtectiveStop) -> bool:
        try:
            mark = self._marks.read()
        except MarkReadError as error:
            self._fail(
                f"the mark price could not be read to place the protective stop ({error})"
            )
            return False
        outcome = self._book.send(stop, mark)
        if outcome.done:
            return True
        logger.warning(
            "Bot %s: the protective stop %s was not placed: %s [protective-stop]",
            self._context.state.bot_id,
            stop.client_order_id,
            outcome.detail,
        )
        self._announce(ProtectiveStopChange.FAILED, outcome.detail)
        fail_with(self._context.state, outcome, "the protective stop")
        return False

    def _fail(self, detail: str) -> None:
        """The stop could not be placed for a reason of the bot's own side: halt, which closes."""
        self._announce(ProtectiveStopChange.FAILED, detail)
        halt_with(self._context.state, GridReason.PROTECTIVE_STOP_FAILED, detail)

    def _open_stops(self) -> dict[str, Order]:
        """The bot's protective stops that stand on the exchange, by client id."""
        return {
            str(order.client_order_id): order
            for order in self._context.gateway.protective_orders()
        }

    # -- cancelling ---------------------------------------------------------

    def _cancel_over_nothing(self) -> None:
        """Stops stand and the account holds no position: read once more, then cancel them."""
        if not self._book.stops:
            return
        again = self._context.gateway.position()
        if again != 0:
            return
        logger.warning(
            "Bot %s: a protective stop stands over a flat %s; cancelling it, because "
            "it could open a position [protective-stop]",
            self._context.state.bot_id,
            self._context.state.bot.definition.symbol,
        )
        self.release()

    def _release(self, stop: ProtectiveStop) -> bool:
        if stop.state is ProtectiveStopState.TRIGGERED:
            self._book.apply(stop, ProtectiveStopEvent.SETTLED)
            return True
        if stop.state is ProtectiveStopState.INTENDED:
            self._book.apply(stop, ProtectiveStopEvent.ACCEPTED)
            stop = self._book.stop_by_id(stop.client_order_id) or stop
        if stop.state is ProtectiveStopState.STANDING:
            self._book.apply(stop, ProtectiveStopEvent.EXPOSURE_CLOSED)
            stop = self._book.stop_by_id(stop.client_order_id) or stop
        return self._cancel_cancelling(stop)

    def _cancel_cancelling(self, stop: ProtectiveStop) -> bool:
        outcome = self._book.cancel(stop)
        if outcome.done:
            self._book.apply(stop, ProtectiveStopEvent.CANCELLED)
            return True
        still_open = set(self._open_stops())
        if stop.client_order_id not in still_open:
            self._book.apply(stop, ProtectiveStopEvent.UNKNOWN_ORDER)
            return True
        logger.warning(
            "Bot %s: the protective stop %s could not be cancelled: %s [protective-stop]",
            self._context.state.bot_id,
            stop.client_order_id,
            outcome.detail,
        )
        return False

    def _announce(self, change: ProtectiveStopChange, detail: str) -> None:
        """Tell the rest of the app (the alert module, `EPIC-036B`) once per occurrence."""
        state = self._context.state
        self._context.events.publish(
            BotProtectiveStopEvent(
                bot_id=state.bot_id,
                symbol=state.bot.definition.symbol,
                change=change,
                detail=detail,
            )
        )

    # -- what is wanted -----------------------------------------------------

    def _wanted(self) -> tuple[_Wanted, ...]:
        params = self._context.params
        if params.direction is TradeDirection.NEUTRAL:
            # A NEUTRAL grid has no stop loss over the range: its exit above is the take
            # profit (`GridReason.TAKE_PROFIT`), so the short side's stop stands there.
            return tuple(
                _Wanted(side, price)
                for side, price in (
                    (OrderSide.SELL, params.stop_loss_price),
                    (OrderSide.BUY, params.take_profit_price),
                )
                if price is not None
            )
        price = params.stop_loss_price
        if price is None:
            return ()
        side = (
            OrderSide.BUY
            if params.direction is TradeDirection.SHORT
            else OrderSide.SELL
        )
        return (_Wanted(side, price),)

    def _covers(self, side: OrderSide, position: Decimal) -> bool:
        """Whether a stop of `side` closes `position` (SELL a long, BUY a short); a NEUTRAL
        grid's other side waits for check T3."""
        if self._context.params.direction is TradeDirection.NEUTRAL and (
            NEUTRAL_BOTH_SIDES_VERIFIED
        ):
            return True
        return position > 0 if side is OrderSide.SELL else position < 0
