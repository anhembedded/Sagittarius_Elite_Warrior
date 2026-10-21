"""`EPIC-039L` — a Futures Grid's exchange-side protective stop: when it is placed, kept, replaced and cancelled.

@details The policy of decisions D4 to D8 of `DECISION_2026-10-16`. The bot's stop-loss price
becomes a `STOP_MARKET` that closes the whole position of the symbol on the mark price. For a
LONG grid it is a SELL under the range, for a SHORT grid a BUY over it; a NEUTRAL grid stands only
the one that covers its position until the owner has recorded check T3 (`protective_stop_plan.py`).

  · **Place** (`protect`, and `supervise` for a stop that is missing): the record is saved
    first, then the order is sent; a refusal by name drops the record and halts the bot, which
    closes its position (it is never left bare); the order is never sent while the account
    holds no position, because it would stand over nothing.
  · **Keep** (`supervise`, on the price watch's beat and after a reconcile): a stop that was
    standing and is on no open list, with the position flat, is judged by the order itself, read
    by its client id: it ran (`TRIGGERED`, the verdict the bot stops on) or the exchange ended
    it without a fill (the record is dropped); an answer that cannot be read counts as ran, the
    side that ends flat. With a position standing it is placed again. A stop on a symbol the
    second read shows flat is cancelled (an orphan would open a position), and a stop that no
    longer covers the position (a NEUTRAL grid whose position changed sign) goes once the
    covering one stands.
  · **Cancel** (`release`): only once the bot's own exposure is closed, never before; a cancel
    that did not go through leaves the stop and the stop of the bot waits.

A look that cannot read the position or the mark changes nothing and says so.
"""

from __future__ import annotations

import logging
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protective_stop_plan import (
    WantedStop,
    covers,
    wanted_stops,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.stop_coverage_reader import (
    StopCoverageReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.unread_streak import (
    UnreadStreak,
    log_unread_stops,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    StopCoverageReading,
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

logger = logging.getLogger("App.Bots.GridExecutor")

#: The states in which the bot holds or lays orders, or is about to again (a restored bot, before
#: its reconcile), and so keeps its position protected.
_SUPERVISED = frozenset(
    {
        BotLifecycleState.RUNNING,
        BotLifecycleState.PAUSED,
        BotLifecycleState.RECOVERING,
    }
)


class ProtectiveStopService(IExposureProtection):
    """The protective stop of one Futures Grid."""

    def __init__(self, context: GridRunContext, marks: IMarkSource) -> None:
        self._context = context
        self._marks = marks
        self._position_unread = UnreadStreak()
        self._book = ProtectiveStopBook(context)
        self._coverage = StopCoverageReader(
            context, lambda: self._book.stops, self._open_stops
        )

    def protect(self, plan: GridPlan) -> bool:
        wanted = wanted_stops(self._context.params)
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
        if state.state not in _SUPERVISED or not wanted_stops(self._context.params):
            return ProtectionVerdict.OK
        position = self._context.gateway.account_reads.watched_position()
        if position is None:
            logger.log(
                self._position_unread.failed(),
                "Bot %s: the position could not be read, so the protective stop is not "
                "looked at this time [protective-stop]",
                state.bot_id,
            )
            return ProtectionVerdict.OK
        self._position_unread.cleared()
        open_stops = self._open_stops()
        if open_stops is None:
            return ProtectionVerdict.OK
        finishing = any(
            s.state is ProtectiveStopState.CANCELLING for s in self._book.stops
        )
        for stop in self._book.stops:
            if self._settle(stop, open_stops, position) is ProtectionVerdict.TRIGGERED:
                return ProtectionVerdict.TRIGGERED
        if finishing:
            # A cancel was finished: the open list read above still names that order.
            open_stops = self._open_stops()
            if open_stops is None:
                return ProtectionVerdict.OK
        if state.state is BotLifecycleState.RECOVERING:
            # Read only: trading takes a tagged order only under the bot's registered budget,
            # which the reconcile registers. What is missing is placed once it has.
            return ProtectionVerdict.OK
        if position == 0:
            self._cancel_over_nothing()
        else:
            self._place_wanted(position, open_stops)
        return ProtectionVerdict.OK

    def describe_stop(self) -> str:
        return self._coverage.describe()

    def read_coverage(self) -> StopCoverageReading:
        return self._coverage.read()

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
            for want in wanted_stops(self._context.params)
            if covers(self._context.params, want.side, position)
        )
        if stood:
            self._cancel_untracked(open_stops)
            self._release_uncovered(position)
        return stood

    def _release_uncovered(self, position: Decimal) -> None:
        """A recorded stop whose side no longer covers `position` (a NEUTRAL grid whose position
        changed sign while the other side's stop stays unverified, check T3) goes, now that the
        one that covers it stands: left, it would close the position of the other side or open
        one."""
        for stop in self._book.stops:
            if not covers(self._context.params, stop.side, position):
                logger.warning(
                    "Bot %s: the protective stop %s no longer covers the position %s; "
                    "cancelling it [protective-stop]",
                    self._context.state.bot_id,
                    stop.client_order_id,
                    position,
                )
                self._release(stop)

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
        if stop.state is ProtectiveStopState.CANCELLING:
            self._finish_cancelling(stop, open_stops, position)
            return None
        if stop.client_order_id in open_stops:
            if stop.state is ProtectiveStopState.INTENDED:
                self._book.apply(stop, ProtectiveStopEvent.ACCEPTED)
            return None
        return self._explain_absence(stop, position)

    def _finish_cancelling(
        self, stop: ProtectiveStop, open_stops: dict[str, Order], position: Decimal
    ) -> None:
        """A cancel that did not finish left the record `CANCELLING` (the bot's exposure was
        closed then). The order gone: the record ends, and a position that stands is protected
        by a new stop. The order still open over a position it covers: the exposure came back,
        so the very order that stands goes on standing (`exposure_reopened`), never cancelled
        and sent again, which would leave the position bare in between (decision D7). Open and
        no longer covering anything: the cancel is finished."""
        if stop.client_order_id not in open_stops:
            self._book.apply(stop, ProtectiveStopEvent.UNKNOWN_ORDER)
        elif covers(self._context.params, stop.side, position):
            self._book.apply(stop, ProtectiveStopEvent.EXPOSURE_REOPENED)
        else:
            self._cancel_cancelling(stop)

    def _explain_absence(
        self, stop: ProtectiveStop, position: Decimal
    ) -> ProtectionVerdict | None:
        """The stop is on no open list. With a position standing it is placed again. With the
        account flat the order itself says how it ended (`_ran`), not the history, which the
        trading side serves up to 15 s old and names a fill by an id the stream may not have
        linked (decision D4)."""
        standing = stop.state is ProtectiveStopState.STANDING
        if standing and position != 0:  # a shared reading may predate the fill
            if (confirmed := self._context.gateway.position()) is None:
                return None  # unread: judged at the next beat
            position = confirmed
        logger.info(
            "Bot %s: protective stop %s %s is on no open list and the position is %s "
            "[protective-stop]",
            self._context.state.bot_id,
            stop.client_order_id,
            stop.state.value,
            position,
        )
        if standing and position == 0 and not self._book.ran(stop):
            self._book.apply(stop, ProtectiveStopEvent.EXPIRED)
            return None
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

    def _place_if_missing(self, want: WantedStop, open_stops: dict[str, Order]) -> bool:
        """Have a stop standing for `want`; `False` when it could not, the bot has moved."""
        held = next((s for s in self._book.stops if s.side is want.side), None)
        if held is not None and held.state is ProtectiveStopState.STANDING:
            return True
        if held is None:
            adopted = self._book.adopt(want.side, want.trigger_price, open_stops)
            if adopted:
                return True
            held = self._book.intend(want.side, want.trigger_price)
        return self._send(held)

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

    def _open_stops(self) -> dict[str, Order] | None:
        """The bot's protective stops that stand on the exchange, by client id; `None` when the
        exchange's open orders could not be read, which is not "none stand"."""
        try:
            orders = self._context.gateway.account_reads.protective_orders()
        except Exception as failure:  # noqa: BLE001 - converted at this seam: an unread list is `None`, never empty
            log_unread_stops(logger, failure, self._context.state.bot_id)
            return None
        return {str(order.client_order_id): order for order in orders}

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
        still_open = self._open_stops()
        if still_open is not None and stop.client_order_id not in still_open:
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
