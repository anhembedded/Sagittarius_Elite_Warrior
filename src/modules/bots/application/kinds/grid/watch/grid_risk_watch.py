"""`EPIC-039F` - a running position bot watches the exchange's liquidation price and its own position.

Two questions, asked on the bot's own queue at each price-watch beat (like `GridTermsWatch`),
and only in the states that hold or lay orders (`PRICE_STALENESS_HALTS`):

  · **How far is the mark from the liquidation price the exchange reports?** The guard
    (`IRiskGuard.watch`) turns the snapshot into a level. A change of level is one
    `BotRiskChangedEvent` (the return to SAFE too, which re-arms the next warning); CRITICAL
    also halts with `GridReason.LIQUIDATION_RISK`. A read that fails keeps the last snapshot,
    which ages into UNKNOWN: a position the bot cannot see is never called SAFE.
  · **Did the position move with no order of ours?** Trading reports a divergence
    (`OwnerPositionDivergedEvent`: a forced close, an ADL, a trade by hand, or a book that
    disagrees). The report can outrun the stream that explains it - `ORDER_TRADE_UPDATE` is
    only assumed to precede `ACCOUNT_UPDATE` - so the watch **confirms before it halts**: after
    `position_recheck_delay` it re-reads (`IPositionRecheck`) and halts only if the divergence
    is still there (`FOREIGN_FILL`, or `POSITION_MISMATCH`). Unconfirmed, it is logged and the
    bot runs on.

  · **A bot that cannot see its position is not safe** (the owner's rule): when the level has
    been UNKNOWN - or no reading ever arrived - for longer than `risk_unknown_halt_after`
    (120 s) and the last known position is not flat, it halts with
    `GridReason.POSITION_UNOBSERVABLE`. A last reading that was flat does not halt it; a
    bot with no reading at all counts as possibly exposed. Any judgeable reading restarts
    the clock.

What the halt then does with the position (close it reduce-only unless an exchange-side stop
stands, decision O8) is the Futures executor's policy (`EPIC-039H`, `039L`), not this watch's.
The watch never changes a parameter and never sends an order.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_order_failure import (
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_risk_changed_event import (
    BotRiskChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_risk_guard import IRiskGuard
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_risk_reads import (
    IPositionRecheck,
    IRiskSnapshotSource,
    RiskReadError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import (
    RiskLevel,
    RiskSnapshot,
    RiskState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    PRICE_STALENESS_HALTS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergence,
    PositionDivergenceKind,
)

logger = logging.getLogger("App.Bots.GridExecutor")


@dataclass(frozen=True, slots=True)
class RiskWatchParts:
    """What the watch asks and with which numbers."""

    guard: IRiskGuard
    snapshots: IRiskSnapshotSource
    rechecks: IPositionRecheck
    clock: IBotClock
    thresholds: FuturesGridThresholds


@dataclass(frozen=True, slots=True)
class _Pending:
    divergence: PositionDivergence
    #: On the bot's monotonic clock.
    due_at: float
    #: The latest `due_at` a newer report may move the re-read to: the first report's time plus
    #: `MAX_RECHECK_DELAYS` delays. A stream that never goes quiet must still get its re-read.
    latest_due_at: float
    #: A newer report moved this re-read, so fills were landing when it was set up.
    moved: bool = False
    #: The re-read that follows a mismatch found after such a burst (`BUG-218`).
    second_look: bool = False

    def moved_to(self, divergence: PositionDivergence, due_at: float) -> _Pending:
        return _Pending(
            divergence, min(due_at, self.latest_due_at), self.latest_due_at, moved=True
        )

    def looked_at_again(
        self, divergence: PositionDivergence, due_at: float
    ) -> _Pending:
        return _Pending(divergence, due_at, due_at, moved=True, second_look=True)


#: How many recheck delays a run of reports may keep one re-read waiting.
MAX_RECHECK_DELAYS = 3


_DIVERGENCE_HALTS = {
    PositionDivergenceKind.POSITION_CHANGED_UNORDERED: GridReason.FOREIGN_FILL,
    PositionDivergenceKind.POSITION_MISMATCH: GridReason.POSITION_MISMATCH,
}


class GridRiskWatch:
    """Judges the liquidation distance and confirms a divergence, one beat at a time."""

    def __init__(self, context: GridRunContext, parts: RiskWatchParts) -> None:
        self._context = context
        self._parts = parts
        self._level = RiskLevel.SAFE
        self._snapshot: RiskSnapshot | None = None
        self._read_failing = False
        self._pending: _Pending | None = None
        #: When the bot stopped being able to judge, on the monotonic clock; `None` while it can.
        self._blind_since: float | None = None

    @property
    def level(self) -> RiskLevel:
        return self._level

    def on_divergence(self, divergence: PositionDivergence) -> None:
        """Trading reported a divergence: confirm it after the recheck delay.

        One re-read is pending at a time (`BUG-218`): a report of the same figures is the same
        divergence, and a report of new figures while one is pending (a burst of fills reports a
        new pair at each) moves that one re-read to the quiet after the last of them, at most
        `MAX_RECHECK_DELAYS` delays after the first, instead of adding a re-read and a line to
        the log for each. The re-read is the only thing here that costs weight: it registers the
        budget again."""
        pending = self._pending
        if pending is not None and pending.divergence.cause == divergence.cause:
            return
        delay = self._parts.thresholds.position_recheck_delay.total_seconds()
        due_at = self._context.monotonic.seconds() + delay
        self._pending = (
            _Pending(divergence, due_at, due_at + (MAX_RECHECK_DELAYS - 1) * delay)
            if pending is None
            else pending.moved_to(divergence, due_at)
        )
        log = logger.info if pending is None else logger.debug
        log(
            "Bot %s: the exchange's position %s differs from the bot's %s (%s); "
            "re-reading in %.0f s before acting%s [position-divergence]",
            self._context.state.bot_id,
            divergence.exchange,
            divergence.derived,
            divergence.kind.value,
            delay,
            "" if pending is None else " (the pending re-read moved)",
        )

    def check(self) -> None:
        """One beat: confirm a pending divergence, then judge the liquidation distance."""
        if self._context.state.state not in PRICE_STALENESS_HALTS:
            self._level = RiskLevel.SAFE
            self._pending = None
            self._blind_since = None
            return
        self._confirm_divergence()
        if self._context.state.state in PRICE_STALENESS_HALTS:
            self._judge_distance()

    # --- the divergence ---

    def _confirm_divergence(self) -> None:
        pending = self._pending
        if pending is None or self._context.monotonic.seconds() < pending.due_at:
            return
        try:
            still = self._parts.rechecks.recheck(pending.divergence)
        except RiskReadError as error:
            logger.warning(
                "Bot %s: the position could not be re-read (%s); asking again "
                "[position-divergence]",
                self._context.state.bot_id,
                error,
            )
            return
        self._pending = None
        if still is None:
            logger.info(
                "Bot %s: the position agrees again after the re-read; left running "
                "[position-divergence]",
                self._context.state.bot_id,
            )
            return
        if pending.moved and not pending.second_look:
            # Fills were landing while this re-read waited, and one can land between the two
            # reads it makes: a mismatch found now may be that fill. Look once more; halt only
            # if it persists (`BUG-218`, the confirm-twice rule of the missed-fill reconcile).
            delay = self._parts.thresholds.position_recheck_delay.total_seconds()
            due_at = self._context.monotonic.seconds() + delay
            self._pending = pending.looked_at_again(still, due_at)
            logger.info(
                "Bot %s: the position still differs after a re-read that followed a burst "
                "of reports; looking once more in %.0f s [position-divergence]",
                self._context.state.bot_id,
                delay,
            )
            return
        detail = (
            f"the exchange holds {still.exchange}, the bot's own fills add up to "
            f"{still.derived}, and they still differ after a re-read"
        )
        logger.error(
            "Bot %s: %s; halting [position-divergence]",
            self._context.state.bot_id,
            detail,
        )
        halt_with(self._context.state, _DIVERGENCE_HALTS[still.kind], detail)

    # --- the distance ---

    def _judge_distance(self) -> None:
        self._read()
        snapshot = self._snapshot
        if snapshot is None:
            self._report_no_reading()
            self._note_blindness(None)
            return
        state = self._parts.guard.watch(snapshot, self._parts.clock.now(), self._level)
        if state.level is not self._level:
            self._level = state.level
            self._announce(state, snapshot)
            if state.level is RiskLevel.CRITICAL:
                halt_with(
                    self._context.state, GridReason.LIQUIDATION_RISK, state.reason
                )
        self._note_blindness(state)

    def _report_no_reading(self) -> None:
        """No reading has ever arrived: the level is UNKNOWN, said once."""
        if self._level is RiskLevel.UNKNOWN:
            return
        self._level = RiskLevel.UNKNOWN
        self._announce(
            RiskState(
                RiskLevel.UNKNOWN, "The exchange's position has not been read yet"
            ),
            None,
        )

    def _note_blindness(self, state: RiskState | None) -> None:
        """Halt once the bot has been unable to judge for longer than the limit."""
        if state is not None and state.level is not RiskLevel.UNKNOWN:
            self._blind_since = None
            return
        now = self._context.monotonic.seconds()
        if self._blind_since is None:
            self._blind_since = now
        limit = self._parts.thresholds.risk_unknown_halt_after.total_seconds()
        last = self._snapshot
        exposed = last is None or last.position != 0
        if now - self._blind_since > limit and exposed:
            detail = (
                f"the exchange's position could not be seen for more than {limit:.0f} s "
                "and the bot may hold one"
            )
            logger.error(
                "Bot %s: %s; halting [liquidation-risk]",
                self._context.state.bot_id,
                detail,
            )
            halt_with(self._context.state, GridReason.POSITION_UNOBSERVABLE, detail)

    def _read(self) -> None:
        try:
            self._snapshot = self._parts.snapshots.read()
        except RiskReadError as error:
            if not self._read_failing:
                logger.warning(
                    "Bot %s: the exchange's position could not be read (%s); the last "
                    "reading ages [liquidation-risk]",
                    self._context.state.bot_id,
                    error,
                )
            self._read_failing = True
            return
        self._read_failing = False

    def _announce(self, state: RiskState, snapshot: RiskSnapshot | None) -> None:
        log = logger.info if state.level is RiskLevel.SAFE else logger.warning
        log(
            "Bot %s: liquidation risk is %s: %s [liquidation-risk]",
            self._context.state.bot_id,
            state.level.value,
            state.reason,
        )
        definition = self._context.state.bot.definition
        self._context.events.publish(
            BotRiskChangedEvent(
                bot_id=self._context.state.bot_id,
                symbol=definition.symbol,
                level=state.level,
                reason=state.reason,
                distance=state.distance,
                mark_price=None if snapshot is None else snapshot.mark_price,
                liquidation_price=None
                if snapshot is None
                else snapshot.liquidation_price,
            )
        )
