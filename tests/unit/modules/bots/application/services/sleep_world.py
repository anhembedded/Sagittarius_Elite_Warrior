"""A running Grid, the watch over it, and a machine that can sleep (`EPIC-035I`).

`Sleeper` moves both clocks the way a suspended laptop does: the wall clock and
(on Windows) the monotonic clock jump together. `sleep(wall_only=True)` is the
Linux case, where the monotonic clock stops while the machine is suspended.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.sleep_watch import (
    SleepWatch,
    SleepWatchDeps,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    FreshPriceUnavailableError,
    IFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.gap_world import (
    running,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    GridWorld,
)


class ScriptedFreshPrice(IFreshPriceReader):
    """Answers the next scripted price (or failure) for every read."""

    def __init__(self, *answers: Decimal | None) -> None:
        self._answers = list(answers)
        self.reads: list[tuple[TradingVenue, str]] = []

    def read(self, venue: TradingVenue, symbol: str) -> Decimal:
        self.reads.append((venue, symbol))
        answer = self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
        if answer is None:
            raise FreshPriceUnavailableError("the venue did not answer")
        return answer


class Sleeper:
    """The bots, their watch, and a machine that can sleep. The heartbeat is not
    begun, so the only thing the scheduler ever holds is a price retry."""

    def __init__(
        self, prices: ScriptedFreshPrice, world: GridWorld | None = None
    ) -> None:
        self.world = world if world is not None else running()
        self.prices = prices
        self.notifier = RecordingNotifier()
        self.executors = BotExecutors(self.world.factory)
        self.executors.for_bot(self.world.store.load(BotId(BOT)).bot)
        self.watch = SleepWatch(
            self.executors,
            SleepWatchDeps(
                monotonic=self.world.monotonic,
                wall=self.world.clock,
                retries=self.world.retries,
                prices=prices,
                notifier=self.notifier,
            ),
        )

    def beat(self, after: timedelta) -> None:
        """Ordinary time passes, then the heartbeat runs."""
        self.world.monotonic.advance(after.total_seconds())
        self.world.clock.advance(after)
        self.watch.check()

    def run_price_retry(self) -> None:
        """The oldest pending price retry runs, as if its time had come."""
        if not self.world.retries.pending:
            raise AssertionError("no price retry is pending")
        self.world.retries.run_next()

    def sleep(self, for_: timedelta, *, wall_only: bool = False) -> None:
        """The machine sleeps `for_`, wakes, and the heartbeat runs."""
        if not wall_only:
            self.world.monotonic.advance(for_.total_seconds())
        self.world.clock.advance(for_)
        self.watch.check()
