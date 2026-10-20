"""The account-level loss cap over doubles shaped from its ports (`EPIC-026L`).

The cap, its sampler and its stopper are the real classes; what they read and write is a bots
world answering the one query and recording every Stop, an in-memory record, a recording
publisher and a clock the test moves. Nothing sleeps: a test calls `sample()` as the ticker would.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.account_loss_cap import (
    AccountLossCap,
    LossCapParts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.loss_cap_sampler import (
    LossCapSampler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.loss_cap_stopper import (
    LossCapStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
    GetBotStatusReportQuery,
    UnreadableBotEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.account_loss_cap_tripped_event import (
    AccountLossCapTrippedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_store import (
    ILossCapStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    RunEarnings,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_figure import (
    parse_loss_cap_figure,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_ledger import (
    LossCapLedger,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_policy import (
    LossCapRecord,
    LossCapTrip,
)
from sagittarius_engine.domain.i_domain_event import IDomainEvent

MORNING = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
RUN = datetime(2026, 10, 20, 2, 0, tzinfo=UTC)


def bot(
    bot_id: str,
    pnl: str | None,
    *,
    state: str = "RUNNING",
    venue: str = "spot_mainnet",
    symbol: str = "BTCUSDT",
    run: datetime | None = RUN,
) -> BotStatusEntry:
    """A bot whose run began today, so its whole account is today's."""
    earnings = (
        None
        if state in {"DRAFT"}
        else RunEarnings(
            grid_profit=Decimal(0),
            completed_cycles=0,
            total_pnl=None if pnl is None else Decimal(pnl),
            judged=True,
        )
    )
    return BotStatusEntry(
        bot_id=bot_id,
        name=f"bot {bot_id}",
        kind="grid",
        venue=venue,
        symbol=symbol,
        state=state,
        reason="",
        run_started_at=run,
        earnings=earnings,
    )


class BotsWorld(ICommandDispatcher):
    """Answers the status report and records every Stop; a Stop is accepted unless refused."""

    def __init__(self, *bots: BotStatusEntry) -> None:
        self.bots = {entry.bot_id: entry for entry in bots}
        self.stops: list[tuple[str, ExposureHandling]] = []
        self.unreadable: tuple[UnreadableBotEntry, ...] = ()
        self.read_raises = False
        self.refuse: dict[str, str] = {}
        self.on_stop: list[str] = []

    def set(self, entry: BotStatusEntry) -> None:
        self.bots[entry.bot_id] = entry

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        if handler_class is GetBotStatusReportQuery:
            if self.read_raises:
                raise RuntimeError("the bots cannot be read")
            return BotStatusReport(
                bots=tuple(self.bots.values()), unreadable=self.unreadable
            )
        if handler_class is StopBotCommand and isinstance(input_dto, StopBotCommand):
            return self._stop(input_dto)
        raise AssertionError(f"the cap asked for {handler_class!r}")

    def _stop(self, command: StopBotCommand) -> BotCommandResult:
        if command.bot_id in self.refuse:
            return BotCommandResult.refused(
                BotRefusal.INVALID_TRANSITION,
                self.refuse[command.bot_id],
                command.bot_id,
            )
        self.stops.append((command.bot_id, command.base))
        self.on_stop.append(command.bot_id)
        self.bots[command.bot_id] = replace(self.bots[command.bot_id], state="STOPPING")
        return BotCommandResult.done(command.bot_id)

    @property
    def stopped_ids(self) -> list[str]:
        return [bot_id for bot_id, _ in self.stops]


class MemoryLossCapStore(ILossCapStore):
    def __init__(self, record: LossCapRecord | None = None) -> None:
        self.record = record
        self.writes: list[LossCapRecord] = []
        self.fails = False

    def read(self) -> LossCapRecord | None:
        return self.record

    def write(self, record: LossCapRecord) -> None:
        if self.fails:
            raise OSError("the disk is full")
        self.writes.append(record)
        self.record = record


class RecordingEvents(IEventPublisher):
    def __init__(self) -> None:
        self.published: list[IDomainEvent] = []

    def publish(self, event: IDomainEvent) -> None:
        self.published.append(event)

    @property
    def trips(self) -> list[AccountLossCapTrippedEvent]:
        return [e for e in self.published if isinstance(e, AccountLossCapTrippedEvent)]


class MovingClock(IBotClock):
    def __init__(self, at: datetime = MORNING) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at

    def advance(self, by: timedelta) -> None:
        self.at += by


@dataclass
class CapWorld:
    cap: AccountLossCap
    bots: BotsWorld
    store: MemoryLossCapStore
    events: RecordingEvents
    clock: MovingClock
    figure: str | None = "500 USDT"
    _notes: list[str] = field(default_factory=list)

    def sample(self) -> None:
        self.cap.sample()

    def restart(self, *, figure: str | None = "500 USDT") -> CapWorld:
        """A new process over what the first one wrote: a fresh cap, the same record and bots."""
        return build(self.bots, figure=figure, store=self.store, clock=self.clock)


def build(
    bots: BotsWorld,
    *,
    figure: str | None = "500 USDT",
    store: MemoryLossCapStore | None = None,
    clock: MovingClock | None = None,
    found_tripped_by: LossCapTrip | None = None,
) -> CapWorld:
    """`found_tripped_by`: the cap boots already tripped, as it does over a record it cannot read."""
    clock = clock or MovingClock()
    store = store or MemoryLossCapStore()
    events = RecordingEvents()
    parsed = parse_loss_cap_figure(figure)
    parts = LossCapParts(
        LossCapSampler(bots, parsed), LossCapStopper(bots), store, events, clock
    )
    record = store.read() or LossCapRecord(
        LossCapLedger.empty(clock.now().date()), found_tripped_by
    )
    cap = AccountLossCap(
        parts, parsed, record, announce_restored_trip=found_tripped_by is not None
    )
    return CapWorld(cap, bots, store, events, clock, figure)
