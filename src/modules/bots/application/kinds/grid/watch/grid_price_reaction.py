"""`EPIC-035A` — what a running Grid does with the price it hears and with its silence.

Split out of `GridExecutor` (the 400-line ceiling, `architecture-rule.md` §5.4):
the actor routes a tick and an age check here, and both run on the bot's worker.

  · **A tick** remembers the price with its moment (`EPIC-035J`), resets the
    bot's price age, and when the tick's *range* reached the stop loss or the take
    profit runs Stop with *sell base* forced, recording why (ADR D11). The range
    is the low and high the bot observed while watching (`GridTickExtremes`,
    `BUG-191`): a wick between two pushes counts, one from before the bot listened
    does not. It is watched while the bot may still hold a position it must
    exit: HALTED and ERROR, and since `EPIC-035A` STARTING and RECOVERING too
    (a start or a recovery may hold the base, and `GridTickExtremes` already
    keeps the pre-start wick out); not STOPPING, whose Stop may keep the base.
  · **The range** (`EPIC-035L`): the same tick also goes to `GridRangeWatch`, which
    publishes a `BotRangeChangedEvent` when the price leaves the range or returns.
    It changes nothing the bot does (D2).
  · **An age check** (`GridPriceAge`) halts a bot that holds orders and heard no
    tick for too long, with `PRICE_FEED_STALE`; in a state a quiet feed does not
    halt it only arms the wait again.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_order_failure import (
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_covered_wait import (
    GridCoveredWait,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stopper import (
    GridStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_range_entry import (
    GridRangeEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_range_watch import (
    GridRangeWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_tick_extremes import (
    GridTickExtremes,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    crossed_exit,
    crossed_exit_in_range,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    RangeExit,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    STREAM_SILENT_AFTER_SECONDS,
)

logger = logging.getLogger("App.Bots.GridExecutor")

_S = BotLifecycleState

_WATCHES_EXITS: frozenset[BotLifecycleState] = frozenset(
    {
        _S.STARTING,
        _S.RUNNING,
        _S.PAUSED,
        _S.RECOVERING,
        _S.HALTED,
        _S.AWAITING_RECOVERY,
        _S.ERROR,
    }
)


#: How often the price the bot heard is saved with its state (`EPIC-035M`): the
#: unrealised PnL is judged on it, and a save per tick would write the file every
#: second.
MARK_PRICE_SAVE_SECONDS: float = 30.0


class GridPriceReaction:
    """Remembers the last price and reacts to a tick and to a quiet feed."""

    def __init__(
        self,
        context: GridRunContext,
        stopper: GridStopper,
        entry: GridRangeEntry,
        covered_wait: GridCoveredWait,
        *,
        exits_on_mark: bool,
    ) -> None:
        """@param entry Lays the ladder of a bot waiting for its range when the price enters it
        (`EPIC-044`); it is handed the price the exits are judged on.
        @param exits_on_mark A position venue's stop loss and take profit are judged on the
        mark (`on_mark`); the streamed last price then only keeps the price and its age.
        @param covered_wait Whether a halt for a quiet feed may wait under the stop (`BUG-270`)."""
        self._context = context
        self._stopper = stopper
        self._entry = entry
        self._exits_on_mark = exits_on_mark
        self._covered_wait = covered_wait
        #: Mark beats the range-exit close still skips: one, armed by an entry (ADR 044 D7).
        self._range_exit_skips = 0
        self._extremes = GridTickExtremes()
        self._mark_saved_at: float | None = None
        self._silence_told = False
        state = context.state
        self._range = GridRangeWatch(
            state.bot_id,
            state.bot.definition.symbol,
            context.params,
            context.events,
        )

    def on_tick(self, tick: PriceTick) -> None:
        self._context.reference_price.note_tick(tick.last)
        self._context.price_age.note_tick()
        self._silence_told = False
        if not self._exits_on_mark:
            self._enter_if_waiting(tick.last)
        if not self._exits_watched():
            self._extremes.reset()
            self._range.reset()
            return
        self._save_mark_price(tick.last)
        self._range.note(tick)
        low, high = self._extremes.observed(tick)
        if not self._exits_on_mark:
            self._exit_if_crossed(tick, low, high, "price")

    def _exits_watched(self) -> bool:
        """The exits are watched while the bot may hold an order or a position (ADR 044 D7)."""
        state = self._context.state
        return state.state in _WATCHES_EXITS and state.may_hold_exposure

    def _enter_if_waiting(self, price: Decimal) -> bool:
        """Hand the price to the entry of a bot waiting for its range; answers whether the bot
        left the wait on it. The price is kept as the bot's last (the Plan says "last price Z" from it, and
        `bot show` the price position), though nothing else of the exits is watched. An entry that
        went on to lay the ladder arms the range-exit close's one skipped beat (ADR 044 D7)."""
        if self._context.state.state is not BotLifecycleState.AWAITING_RANGE:
            return False
        self._save_mark_price(price)
        self._entry.on_price(price)
        if self._context.state.state is BotLifecycleState.AWAITING_RANGE:
            return False
        self._range_exit_skips = 1
        return True

    def on_mark(self, tick: PriceTick) -> None:
        """The mark price of a position venue's symbol: the price its exits are judged on.
        A mark read over REST is a price heard, so the age check does not halt a bot whose
        stream went quiet while the mark answers (`BUG-270`)."""
        self._context.price_age.note_poll()
        self._say_stream_is_silent()
        if self._enter_if_waiting(tick.last):
            return
        if not self._exits_watched():
            return
        self._exit_if_crossed(tick, tick.low, tick.high, "mark price")
        if self._exits_watched():
            self._close_if_out_of_range(tick.last)

    def _say_stream_is_silent(self) -> None:
        """Once per silence: the stream is quiet and the bot lives on the price it reads over REST."""
        silence = self._context.price_age.stream_silence()
        if (
            silence is None
            or silence < STREAM_SILENT_AFTER_SECONDS
            or self._silence_told
        ):
            return
        self._silence_told = True
        logger.warning(
            "Bot %s: the price stream has been quiet for %d s; the bot judges its exits on the "
            "mark price it reads over REST and does not halt for a quiet feed while that answers "
            "[price-poll]",
            self._context.state.bot_id,
            int(silence),
        )

    def _close_if_out_of_range(self, mark: Decimal) -> None:
        params = self._context.params
        if params.on_range_exit is not RangeExit.CLOSE:
            return
        if self._range_exit_skips > 0:
            self._range_exit_skips -= 1
            return
        if params.lower <= mark <= params.upper:
            return
        side = "below" if mark < params.lower else "above"
        edge = params.lower if mark < params.lower else params.upper
        logger.info(
            "Bot %s: the mark price %s left the range, %s %s; closing [range-exit]",
            self._context.state.bot_id,
            mark,
            side,
            edge,
        )
        self._stopper.run(
            ExposureHandling.CLOSE_AT_MARKET,
            GridReason.RANGE_EXIT,
            f"mark price {mark} is {side} the range edge {edge}",
        )

    def _exit_if_crossed(
        self, tick: PriceTick, low: Decimal, high: Decimal, what: str
    ) -> None:
        params = self._context.params
        stop, take = params.stop_loss_price, params.take_profit_price
        reason = crossed_exit_in_range(low, high, stop, take, params.direction)
        if reason is None:
            return
        detail = f"{what} {tick.last}"
        if crossed_exit(tick.last, stop, take, params.direction) is not reason:
            # Once: the Stop this starts leaves every state that watches exits.
            word, extreme, threshold = _wick_of(
                reason, params.direction, low, high, stop, take
            )
            detail = f"{what} {tick.last}, traded to {extreme}"
            logger.info(
                "Bot %s: %s fires on a wick, not on the close: close %s, %s %s, "
                "threshold %s [exit-on-extreme]",
                self._context.state.bot_id,
                reason.value,
                tick.last,
                word,
                extreme,
                threshold,
            )
        self._stopper.run(ExposureHandling.CLOSE_AT_MARKET, reason, detail)

    def _save_mark_price(self, price: Decimal) -> None:
        now = self._context.monotonic.seconds()
        if (
            self._mark_saved_at is not None
            and now - self._mark_saved_at < MARK_PRICE_SAVE_SECONDS
        ):
            return
        self._mark_saved_at = now
        state = self._context.state
        state.update(
            replace(state.runtime, mark_price=price, mark_price_at=state.now())
        )

    def check_age(self) -> None:
        state = self._context.state
        age = self._context.price_age
        if not state.exposure_watched:
            age.arm()
        elif (detail := age.stale_detail()) is not None:
            age.arm()
            halt_with(
                state,
                GridReason.PRICE_FEED_STALE,
                detail,
                self._covered_wait.halt_plain_words(),
            )


def _wick_of(
    reason: GridReason,
    direction: TradeDirection,
    low: Decimal,
    high: Decimal,
    stop: Decimal | None,
    take: Decimal | None,
) -> tuple[str, Decimal, Decimal | None]:
    """Which extreme of the beat reached the exit that fired, and the exit's price: a stop loss
    is reached by the low for a LONG grid and by the high for a SHORT one, a take profit by the
    other (`EPIC-039I`)."""
    stop_hit = reason is GridReason.STOP_LOSS
    by_low = stop_hit is (direction is not TradeDirection.SHORT)
    return (
        ("low", low, stop if stop_hit else take)
        if by_low
        else (
            "high",
            high,
            stop if stop_hit else take,
        )
    )
