"""`EPIC-029B` — every use case goes through the lifecycle table, refuses as a value."""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot import (
    GetBotQuery,
    GetBotQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
    ListBotsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_restore_service import (
    BotRestoreService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
    CreateBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot.handler import (
    MAX_ID_ATTEMPTS,
    IdSpaceExhaustedError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot import (
    DeleteBotCommand,
    DeleteBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot import (
    EditBotCommand,
    EditBotCommandHandler,
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
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
    FakeBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import (
    BotId,
    BotIdGenerator,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import (
    seed,
    state_of,
)

S = BotLifecycleState


class _ScriptedIds(BotIdGenerator):
    """Draws the ids it was given, in order."""

    def __init__(self, *ids: str) -> None:
        self._ids = list(ids)

    def next_id(self) -> BotId:
        return BotId(self._ids.pop(0))


@pytest.fixture
def store() -> FakeBotStore:
    return FakeBotStore()


@pytest.fixture
def clock() -> FakeBotClock:
    return FakeBotClock()


def _create(store: FakeBotStore, clock: FakeBotClock, *ids: str) -> str | None:
    handler = CreateBotCommandHandler(store, clock, _ScriptedIds(*ids))
    result = handler.execute(
        CreateBotCommand(" grid one ", "grid", TradingVenue.SPOT_TESTNET, "btcusdt")
    )
    assert result.accepted
    return result.bot_id


# --- create -----------------------------------------------------------------


def test_create_saves_a_draft_stamped_by_the_clock(
    store: FakeBotStore, clock: FakeBotClock
) -> None:
    bot_id = _create(store, clock, "abc123")
    stored = store.load(BotId("abc123")).bot
    assert bot_id == "abc123"
    assert stored.state is S.DRAFT
    assert stored.created_at == FAKE_CLOCK_START
    assert stored.definition.name == "grid one"
    assert stored.definition.symbol == "BTCUSDT"


def test_create_retries_an_id_that_is_taken(
    store: FakeBotStore, clock: FakeBotClock
) -> None:
    seed(store, "aaa111", S.DRAFT)
    store.refuse_file(BotId("bbb222"), "unknown schema_version 2")
    assert _create(store, clock, "aaa111", "bbb222", "ccc333") == "ccc333"


def test_create_gives_up_after_too_many_collisions(
    store: FakeBotStore, clock: FakeBotClock
) -> None:
    seed(store, "aaa111", S.DRAFT)
    handler = CreateBotCommandHandler(
        store, clock, _ScriptedIds(*["aaa111"] * MAX_ID_ATTEMPTS)
    )
    with pytest.raises(IdSpaceExhaustedError):
        handler.execute(
            CreateBotCommand("n", "grid", TradingVenue.SPOT_TESTNET, "BTCUSDT")
        )


def test_create_refuses_a_definition_without_a_name(
    store: FakeBotStore, clock: FakeBotClock
) -> None:
    handler = CreateBotCommandHandler(store, clock, _ScriptedIds("abc123"))
    result = handler.execute(
        CreateBotCommand("  ", "grid", TradingVenue.SPOT_TESTNET, "BTCUSDT")
    )
    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert store.load_all().bots == ()


# --- start ------------------------------------------------------------------


@pytest.mark.parametrize("origin", [S.DRAFT, S.STOPPED])
def test_start_moves_the_bot_to_starting_and_stamps_the_run(
    store: FakeBotStore, clock: FakeBotClock, origin: S
) -> None:
    seed(store, "abc123", origin)
    result = StartBotCommandHandler(store, clock).execute(StartBotCommand("abc123"))
    assert result.accepted
    stored = store.load(BotId("abc123"))
    assert stored.bot.state is S.STARTING
    assert stored.bot.lifecycle.run_started_at == FAKE_CLOCK_START
    assert dict(stored.runtime) == {"cycles": 1}


@pytest.mark.parametrize(
    "other",
    [S.STARTING, S.RUNNING, S.PAUSED, S.RECOVERING, S.HALTED, S.STOPPING, S.ERROR],
)
def test_a_second_bot_cannot_start_while_one_is_active(
    store: FakeBotStore, clock: FakeBotClock, other: S
) -> None:
    seed(store, "aaa111", other)
    seed(store, "bbb222", S.DRAFT)
    result = StartBotCommandHandler(store, clock).execute(StartBotCommand("bbb222"))
    assert result.refusal is BotRefusal.ONE_RUNNING_BOT_DURING_FAST_TRACK
    assert "aaa111" in result.message
    assert state_of(store, "bbb222") is S.DRAFT


def test_an_unreadable_file_counts_as_an_active_bot(
    store: FakeBotStore, clock: FakeBotClock
) -> None:
    store.refuse_file(BotId("aaa111"), "unknown schema_version 2")
    seed(store, "bbb222", S.DRAFT)
    result = StartBotCommandHandler(store, clock).execute(StartBotCommand("bbb222"))
    assert result.refusal is BotRefusal.ONE_RUNNING_BOT_DURING_FAST_TRACK


@pytest.mark.parametrize("other", [S.DRAFT, S.STOPPED])
def test_idle_bots_do_not_block_a_start(
    store: FakeBotStore, clock: FakeBotClock, other: S
) -> None:
    seed(store, "aaa111", other)
    seed(store, "bbb222", S.DRAFT)
    assert (
        StartBotCommandHandler(store, clock).execute(StartBotCommand("bbb222")).accepted
    )


def test_starting_a_running_bot_is_an_invalid_transition(
    store: FakeBotStore, clock: FakeBotClock
) -> None:
    seed(store, "abc123", S.RUNNING)
    result = StartBotCommandHandler(store, clock).execute(StartBotCommand("abc123"))
    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert state_of(store, "abc123") is S.RUNNING


@pytest.mark.parametrize("bot_id", ["zzz999", "NOT-AN-ID"])
def test_an_unknown_bot_is_refused_as_not_found(
    store: FakeBotStore, clock: FakeBotClock, bot_id: str
) -> None:
    result = StartBotCommandHandler(store, clock).execute(StartBotCommand(bot_id))
    assert result.refusal is BotRefusal.NOT_FOUND


def test_a_bot_whose_file_is_unreadable_is_refused_as_unreadable(
    store: FakeBotStore, clock: FakeBotClock
) -> None:
    store.refuse_file(BotId("abc123"), "bad json")
    result = PauseBotCommandHandler(store, clock).execute(PauseBotCommand("abc123"))
    assert result.refusal is BotRefusal.UNREADABLE


# --- pause, resume, stop ----------------------------------------------------


@pytest.mark.parametrize(
    ("origin", "run", "expected"),
    [
        (S.RUNNING, "pause", S.PAUSED),
        (S.PAUSED, "resume", S.RUNNING),
        (S.HALTED, "resume", S.STARTING),
        (S.RUNNING, "stop", S.STOPPING),
        (S.ERROR, "stop", S.STOPPING),
    ],
)
def test_lifecycle_commands_follow_the_table(
    store: FakeBotStore, clock: FakeBotClock, origin: S, run: str, expected: S
) -> None:
    seed(store, "abc123", origin)
    handlers = {
        "pause": lambda: PauseBotCommandHandler(store, clock).execute(
            PauseBotCommand("abc123")
        ),
        "resume": lambda: ResumeBotCommandHandler(store, clock).execute(
            ResumeBotCommand("abc123")
        ),
        "stop": lambda: StopBotCommandHandler(store, clock).execute(
            StopBotCommand("abc123", BaseHandling.KEEP)
        ),
    }
    assert handlers[run]().accepted
    assert state_of(store, "abc123") is expected


def test_pause_while_starting_is_refused_and_saves_nothing(
    store: FakeBotStore, clock: FakeBotClock
) -> None:
    seed(store, "abc123", S.STARTING)
    result = PauseBotCommandHandler(store, clock).execute(PauseBotCommand("abc123"))
    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert state_of(store, "abc123") is S.STARTING


# --- edit and delete ---------------------------------------------------------


def test_edit_a_stopped_bot_lands_on_draft_with_the_new_parameters(
    store: FakeBotStore, clock: FakeBotClock
) -> None:
    seed(store, "abc123", S.STOPPED)
    result = EditBotCommandHandler(store, clock).execute(
        EditBotCommand("abc123", "renamed", {"lower": "61000"})
    )
    assert result.accepted
    bot = store.load(BotId("abc123")).bot
    assert bot.state is S.DRAFT
    assert bot.definition.name == "renamed"
    assert bot.definition.config == {"lower": "61000"}
    assert bot.definition.symbol == "BTCUSDT"


def test_edit_a_running_bot_is_refused(
    store: FakeBotStore, clock: FakeBotClock
) -> None:
    seed(store, "abc123", S.RUNNING)
    result = EditBotCommandHandler(store, clock).execute(
        EditBotCommand("abc123", "renamed")
    )
    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert store.load(BotId("abc123")).bot.definition.name == "grid one"


def test_edit_refuses_an_empty_name(store: FakeBotStore, clock: FakeBotClock) -> None:
    seed(store, "abc123", S.DRAFT)
    result = EditBotCommandHandler(store, clock).execute(EditBotCommand("abc123", " "))
    assert result.refusal is BotRefusal.INVALID_DEFINITION


@pytest.mark.parametrize("origin", [S.DRAFT, S.STOPPED])
def test_delete_from_draft_or_stopped(store: FakeBotStore, origin: S) -> None:
    seed(store, "abc123", origin)
    assert DeleteBotCommandHandler(store).execute(DeleteBotCommand("abc123")).accepted
    assert not store.exists(BotId("abc123"))


@pytest.mark.parametrize("origin", [s for s in S if s not in {S.DRAFT, S.STOPPED}])
def test_delete_from_any_other_state_is_refused(store: FakeBotStore, origin: S) -> None:
    seed(store, "abc123", origin)
    result = DeleteBotCommandHandler(store).execute(DeleteBotCommand("abc123"))
    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert store.exists(BotId("abc123"))


# --- queries ----------------------------------------------------------------


def test_list_shows_bots_oldest_first_and_names_refused_files(
    store: FakeBotStore, clock: FakeBotClock
) -> None:
    _create(store, clock, "bbb222")
    clock.advance(timedelta(minutes=1))
    _create(store, clock, "aaa111")
    store.refuse_file(BotId("ccc333"), "unknown schema_version 2")

    listed = ListBotsQueryHandler(store).execute(ListBotsQuery())

    assert [bot.bot_id for bot in listed.bots] == ["bbb222", "aaa111"]
    assert [r.name for r in listed.refused] == ["ccc333.json"]


def test_get_returns_a_snapshot_or_none(store: FakeBotStore) -> None:
    seed(store, "abc123", S.PAUSED)
    snapshot = GetBotQueryHandler(store).execute(GetBotQuery("abc123"))
    assert snapshot is not None
    assert snapshot.state is S.PAUSED
    assert snapshot.symbol == "BTCUSDT"
    assert GetBotQueryHandler(store).execute(GetBotQuery("zzz999")) is None
    assert GetBotQueryHandler(store).execute(GetBotQuery("bad id")) is None


# --- restore ----------------------------------------------------------------


def test_restore_applies_d12_saves_changes_and_names_refused_files(
    store: FakeBotStore, clock: FakeBotClock, caplog: pytest.LogCaptureFixture
) -> None:
    seed(store, "run111", S.RUNNING)
    seed(store, "sta222", S.STARTING)
    seed(store, "sto333", S.STOPPED)
    store.refuse_file(BotId("bad444"), "unknown schema_version 2")

    with caplog.at_level(logging.ERROR, logger="App.Bots.Restore"):
        BotRestoreService(store, clock).restore_all()

    assert state_of(store, "run111") is S.RECOVERING
    assert store.load(BotId("run111")).bot.lifecycle.recovering_from is S.RUNNING
    assert state_of(store, "sta222") is S.HALTED
    assert state_of(store, "sto333") is S.STOPPED
    assert any("bad444.json" in r.getMessage() for r in caplog.records)
