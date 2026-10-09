"""`EPIC-029B`/`EPIC-029E` — the lifecycle commands: start through its runner
under the D20 lock, and pause, resume and stop checked against the table and
queued on the bot's executor (ADR D9, D20)."""

from __future__ import annotations

import threading

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.resume_readiness import (
    ResumeReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
    ConfirmBotResumeCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot import (
    PauseBotCommand,
    PauseBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
    ResumeBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
    StartBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
    StopBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import (
    BotId,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import (
    seed,
    state_of,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    readiness_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
)

S = BotLifecycleState


@pytest.fixture
def world() -> ReadinessWorld:
    """A funded Spot Testnet account and a venue; its store is the one the
    handlers share, and no bot is in it until a test seeds one."""
    made = readiness_world()
    made.store.delete(BotId(BOT))
    return made


@pytest.fixture
def store(world: ReadinessWorld) -> FakeBotStore:
    return world.store


@pytest.fixture
def clock(world: ReadinessWorld) -> FakeBotClock:
    return world.clock


class _RecordingRunner(IBotRunner):
    """`IBotRunner` as its contract states it: a start that passes leaves the
    bot STARTING; every other command is queued (recorded here)."""

    def __init__(self, store: FakeBotStore, clock: FakeBotClock) -> None:
        self._store = store
        self._clock = clock
        self.refusal: BotCommandResult | None = None
        self.sent: list[tuple[str, str]] = []
        self.proposals: set[str] = set()

    def start(self, bot_id: str) -> BotCommandResult:
        self.sent.append(("start", bot_id))
        if self.refusal is not None:
            return self.refusal
        stored = self._store.load(BotId(bot_id))
        started = stored.bot.apply(BotLifecycleEvent.START, self._clock.now())
        self._store.save(StoredBot(started, stored.runtime))
        return BotCommandResult.done(bot_id)

    def pause(self, bot_id: str) -> None:
        self.sent.append(("pause", bot_id))

    def resume(self, bot_id: str) -> None:
        self.sent.append(("resume", bot_id))

    def stop(self, bot_id: str, base: BaseHandling) -> None:
        self.sent.append((f"stop:{base.value}", bot_id))

    def confirm_resume(self, bot_id: str) -> None:
        self.sent.append(("confirm_resume", bot_id))

    def has_resume_proposal(self, bot_id: str) -> bool:
        return bot_id in self.proposals


@pytest.fixture
def runner(store: FakeBotStore, clock: FakeBotClock) -> _RecordingRunner:
    return _RecordingRunner(store, clock)


def _handler(
    world: ReadinessWorld, runner: IBotRunner, lock: BotCommandLock | None = None
) -> StartBotCommandHandler:
    return StartBotCommandHandler(
        world.store, runner, lock or BotCommandLock(), world.reader, world.clock
    )


def _start(
    world: ReadinessWorld, runner: _RecordingRunner, bot_id: str
) -> BotCommandResult:
    return _handler(world, runner).execute(StartBotCommand(bot_id))


def _ready(store: FakeBotStore, bot_id: str, state: S) -> None:
    """A bot whose parameters every constraint accepts."""
    seed(store, bot_id, state, CONFIG)


def test_start_hands_the_bot_to_the_runner(
    world: ReadinessWorld, runner: _RecordingRunner
) -> None:
    _ready(world.store, "abc123", S.DRAFT)

    result = _start(world, runner, "abc123")

    assert result.accepted
    assert runner.sent == [("start", "abc123")]
    assert state_of(world.store, "abc123") is S.STARTING


def test_a_refused_precondition_is_the_answer_and_changes_nothing(
    world: ReadinessWorld, runner: _RecordingRunner
) -> None:
    _ready(world.store, "abc123", S.DRAFT)
    runner.refusal = BotCommandResult.refused(
        BotRefusal.SYMBOL_LEASED, "BTCUSDT is held by another owner", "abc123"
    )

    result = _start(world, runner, "abc123")

    assert result.refusal is BotRefusal.SYMBOL_LEASED
    assert state_of(world.store, "abc123") is S.DRAFT


@pytest.mark.parametrize(
    "other",
    [S.STARTING, S.RUNNING, S.PAUSED, S.RECOVERING, S.HALTED, S.STOPPING, S.ERROR],
)
def test_a_second_bot_cannot_start_while_one_is_active(
    world: ReadinessWorld, runner: _RecordingRunner, other: S
) -> None:
    _ready(world.store, "aaa111", other)
    _ready(world.store, "bbb222", S.DRAFT)
    result = _start(world, runner, "bbb222")
    assert result.refusal is BotRefusal.ONE_RUNNING_BOT_DURING_FAST_TRACK
    assert "aaa111" in result.message
    assert state_of(world.store, "bbb222") is S.DRAFT
    assert runner.sent == []


def test_an_unreadable_file_counts_as_an_active_bot(
    world: ReadinessWorld, runner: _RecordingRunner
) -> None:
    world.store.refuse_file(BotId("aaa111"), "unknown schema_version 2")
    _ready(world.store, "bbb222", S.DRAFT)
    result = _start(world, runner, "bbb222")
    assert result.refusal is BotRefusal.ONE_RUNNING_BOT_DURING_FAST_TRACK


@pytest.mark.parametrize("other", [S.DRAFT, S.STOPPED])
def test_idle_bots_do_not_block_a_start(
    world: ReadinessWorld, runner: _RecordingRunner, other: S
) -> None:
    _ready(world.store, "aaa111", other)
    _ready(world.store, "bbb222", S.DRAFT)
    assert _start(world, runner, "bbb222").accepted


def test_two_starts_racing_let_exactly_one_bot_start(world: ReadinessWorld) -> None:
    """The PR #318 review: the D20 check and the start are one step under the
    shared lock, so two starts at once cannot both find no other bot active."""
    _ready(world.store, "aaa111", S.DRAFT)
    _ready(world.store, "bbb222", S.DRAFT)
    inside = threading.Event()
    release = threading.Event()

    class _SlowRunner(_RecordingRunner):
        def start(self, bot_id: str) -> BotCommandResult:
            inside.set()
            release.wait(timeout=5)
            return super().start(bot_id)

    lock = BotCommandLock()
    slow = _SlowRunner(world.store, world.clock)
    results: dict[str, BotCommandResult] = {}

    def first() -> None:
        results["aaa111"] = _handler(world, slow, lock).execute(
            StartBotCommand("aaa111")
        )

    racer = threading.Thread(target=first)
    racer.start()
    assert inside.wait(timeout=5)
    second = threading.Thread(
        target=lambda: results.__setitem__(
            "bbb222", _handler(world, slow, lock).execute(StartBotCommand("bbb222"))
        )
    )
    second.start()
    release.set()
    racer.join(timeout=5)
    second.join(timeout=5)

    assert results["aaa111"].accepted
    assert results["bbb222"].refusal is BotRefusal.ONE_RUNNING_BOT_DURING_FAST_TRACK


@pytest.mark.parametrize("bot_id", ["zzz999", "NOT-AN-ID"])
def test_an_unknown_bot_is_refused_as_not_found(
    store: FakeBotStore, runner: _RecordingRunner, bot_id: str
) -> None:
    result = PauseBotCommandHandler(store, runner).execute(PauseBotCommand(bot_id))
    assert result.refusal is BotRefusal.NOT_FOUND


def test_a_bot_whose_file_is_unreadable_is_refused_as_unreadable(
    store: FakeBotStore, runner: _RecordingRunner
) -> None:
    store.refuse_file(BotId("abc123"), "bad json")
    result = PauseBotCommandHandler(store, runner).execute(PauseBotCommand("abc123"))
    assert result.refusal is BotRefusal.UNREADABLE


# --- pause, resume, stop ----------------------------------------------------


@pytest.mark.parametrize(
    ("origin", "run", "sent"),
    [
        (S.RUNNING, "pause", "pause"),
        (S.PAUSED, "resume", "resume"),
        (S.HALTED, "resume", "resume"),
        (S.RUNNING, "stop", "stop:KEEP"),
        (S.ERROR, "stop", "stop:KEEP"),
    ],
)
def test_a_declared_command_is_queued_on_the_bots_executor(
    world: ReadinessWorld,
    store: FakeBotStore,
    runner: _RecordingRunner,
    origin: S,
    run: str,
    sent: str,
) -> None:
    """The executor is the bot's one writer (ADR D9): the use case checks the
    table and queues; the state does not change here."""
    seed(store, "abc123", origin, runtime={})
    handlers = {
        "pause": lambda: PauseBotCommandHandler(store, runner).execute(
            PauseBotCommand("abc123")
        ),
        "resume": lambda: ResumeBotCommandHandler(
            store, runner, ResumeReadinessReader(world.facts, world.ports, world.caps)
        ).execute(ResumeBotCommand("abc123")),
        "stop": lambda: StopBotCommandHandler(store, runner).execute(
            StopBotCommand("abc123", BaseHandling.KEEP)
        ),
    }
    assert handlers[run]().accepted
    assert runner.sent == [(sent, "abc123")]
    assert state_of(store, "abc123") is origin


def test_stop_carries_the_users_choice_for_the_base(
    store: FakeBotStore, runner: _RecordingRunner
) -> None:
    seed(store, "abc123", S.RUNNING)

    StopBotCommandHandler(store, runner).execute(
        StopBotCommand("abc123", BaseHandling.SELL_AT_MARKET)
    )

    assert runner.sent == [("stop:SELL_AT_MARKET", "abc123")]


def test_pause_while_starting_is_refused_and_queues_nothing(
    store: FakeBotStore, runner: _RecordingRunner
) -> None:
    seed(store, "abc123", S.STARTING)
    result = PauseBotCommandHandler(store, runner).execute(PauseBotCommand("abc123"))
    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert runner.sent == []
    assert state_of(store, "abc123") is S.STARTING


# --- confirm resume (PR #333 review) -----------------------------------------


def _confirm(store: FakeBotStore, runner: _RecordingRunner) -> BotCommandResult:
    return ConfirmBotResumeCommandHandler(store, runner).execute(
        ConfirmBotResumeCommand("abc123")
    )


def test_confirm_with_nothing_proposed_is_refused_and_queues_nothing(
    store: FakeBotStore, runner: _RecordingRunner
) -> None:
    """A HALTED bot whose executor holds no proposal (none asked for yet, or
    the app restarted) would confirm nothing; the screen must not say done."""
    seed(store, "abc123", S.HALTED)

    result = _confirm(store, runner)

    assert result.refusal is BotRefusal.NO_RESUME_PROPOSAL
    assert "Resume" in result.message
    assert runner.sent == []


def test_confirm_of_a_proposed_resume_is_queued(
    store: FakeBotStore, runner: _RecordingRunner
) -> None:
    seed(store, "abc123", S.HALTED)
    runner.proposals.add("abc123")

    assert _confirm(store, runner).accepted
    assert runner.sent == [("confirm_resume", "abc123")]


def test_confirm_outside_halted_is_refused_by_the_table_first(
    store: FakeBotStore, runner: _RecordingRunner
) -> None:
    seed(store, "abc123", S.RUNNING)
    runner.proposals.add("abc123")

    assert _confirm(store, runner).refusal is BotRefusal.INVALID_TRANSITION
    assert runner.sent == []
