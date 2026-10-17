"""`EPIC-038C` — the one bot status read model agrees with the Bots tab's own list."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.running_bots_objection import (
    _AT_REST,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    AT_REST_STATES,
    UNREADABLE_STATE,
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
    is_declared,
    next_target,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
    LevelOrder,
    RuntimeLevel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import seed
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.status_world import (
    BOTS_DIRECTORY,
    BotQueryDispatcher,
    HeldProbe,
)


def _seeded() -> tuple[FakeBotStore, BotQueryDispatcher]:
    store = FakeBotStore()
    seed(store, "aaaaaa", BotLifecycleState.RUNNING)
    seed(store, "bbbbbb", BotLifecycleState.HALTED)
    seed(store, "cccccc", BotLifecycleState.DRAFT)
    store.refuse_file(BotId("dddddd"), "schema_version 99 is newer than this build")
    return store, BotQueryDispatcher(store)


def _report(
    dispatcher: BotQueryDispatcher, bot_id: str | None = None
) -> BotStatusReport:
    report = dispatcher.dispatch(
        GetBotStatusReportQuery, GetBotStatusReportQuery(bot_id)
    )
    assert isinstance(report, BotStatusReport)
    return report


def test_the_report_agrees_with_the_bots_tab_list_on_every_bot() -> None:
    _, dispatcher = _seeded()

    screen = dispatcher.dispatch(ListBotsQuery, ListBotsQuery())
    assert isinstance(screen, BotList)
    report = _report(dispatcher)

    assert [bot.bot_id for bot in report.bots] == [bot.bot_id for bot in screen.bots]
    for row, shown in zip(report.bots, screen.bots, strict=True):
        assert (row.name, row.kind, row.symbol, row.state, row.run_started_at) == (
            shown.name,
            shown.kind,
            shown.symbol,
            shown.state.value,
            shown.run_started_at,
        )
        assert row.venue == shown.venue.value


def test_the_report_is_built_from_the_tabs_queries_not_from_the_store() -> None:
    _, dispatcher = _seeded()

    _report(dispatcher)

    assert dispatcher.asked == [GetBotStatusReportQuery, ListBotsQuery]


def test_an_unreadable_bot_file_is_listed_with_its_path() -> None:
    _, dispatcher = _seeded()

    report = _report(dispatcher)

    assert [(u.bot_id, u.state, u.path, u.reason) for u in report.unreadable] == [
        (
            "dddddd",
            UNREADABLE_STATE,
            str(BOTS_DIRECTORY / "dddddd.json"),
            "schema_version 99 is newer than this build",
        )
    ]
    assert report.state_counts()[UNREADABLE_STATE] == 1


def test_one_bot_by_id_and_an_unreadable_one_by_id() -> None:
    _, dispatcher = _seeded()

    assert [b.bot_id for b in _report(dispatcher, "bbbbbb").bots] == ["bbbbbb"]
    refused = _report(dispatcher, "dddddd")
    assert refused.bots == ()
    assert [u.bot_id for u in refused.unreadable] == ["dddddd"]


def test_an_unknown_id_gives_an_empty_report() -> None:
    _, dispatcher = _seeded()

    assert _report(dispatcher, "zzzzzz").is_empty


def test_health_stays_empty_until_the_bot_health_snapshot_exists() -> None:
    _, dispatcher = _seeded()

    assert all(dict(bot.health) == {} for bot in _report(dispatcher).bots)


def test_the_report_says_whether_a_copy_of_the_app_is_running() -> None:
    store = FakeBotStore()
    seed(store, "aaaaaa", BotLifecycleState.RUNNING)
    for held in (True, False):
        report = BotQueryDispatcher(store, HeldProbe(held)).dispatch(
            GetBotStatusReportQuery, GetBotStatusReportQuery()
        )
        assert isinstance(report, BotStatusReport)
        assert report.app_running is held
        assert report.payload()["app_running"] is held


def test_the_report_counts_the_orders_each_bot_has_resting() -> None:
    """`EPIC-038D`: a host that stops must say how many orders it leaves on the
    exchange, from the same read model `status` prints."""
    store = FakeBotStore()
    bot = seed(store, "aaaaaa", BotLifecycleState.RUNNING)
    seed(store, "bbbbbb", BotLifecycleState.DRAFT, runtime={})
    buy = LevelOrder("SEW-aaaaaa-0000000001", OrderSide.BUY, Decimal(99), Decimal(1))
    sell = LevelOrder("SEW-aaaaaa-0000000002", OrderSide.SELL, Decimal(101), Decimal(1))
    runtime = GridRuntime(
        (
            RuntimeLevel(0, Decimal(99), Decimal(1), LevelState.RESTING, buy),
            RuntimeLevel(1, Decimal(101), Decimal(1), LevelState.RESTING, sell),
        )
    )
    store.save(StoredBot(bot, dict(encode_runtime(runtime))))

    report = _report(BotQueryDispatcher(store))

    resting = {entry.bot_id: entry.resting_orders for entry in report.bots}
    assert resting["aaaaaa"] == 2
    assert resting["bbbbbb"] is None  # a draft has no run, so nothing is known
    assert [b["resting_orders"] for b in report.payload()["bots"]] == [2, None]  # type: ignore[index, union-attr]


def test_the_report_carries_the_words_the_bot_wrote_beside_its_reason() -> None:
    """`EPIC-042D`: the sentence that says the automatic recoveries are used up is in the bot's
    record only; the alert reads it from this entry."""
    store = FakeBotStore()
    bot = seed(store, "aaaaaa", BotLifecycleState.HALTED)
    detail = "the 3 automatic recoveries allowed in 24 h are used up; resume by hand"
    runtime = GridRuntime(()).with_reason(GridReason.PRICE_FEED_STALE, detail)
    store.save(StoredBot(bot, dict(encode_runtime(runtime))))

    [entry] = _report(BotQueryDispatcher(store)).bots

    assert entry.reason == GridReason.PRICE_FEED_STALE.value
    assert entry.reason_detail == detail


@pytest.mark.parametrize("state", list(BotLifecycleState), ids=lambda s: s.value)
def test_the_report_says_which_bots_a_restart_makes_recovering_from_the_lifecycle_table(
    state: BotLifecycleState,
) -> None:
    """`EPIC-038D`: the host refuses a mainnet resume for every bot the restart rule will
    make RECOVERING, and the report is the only place that may say which those are - from
    the lifecycle table itself, not from a second list."""
    store = FakeBotStore()
    seed(store, "aaaaaa", state)

    entry = _report(BotQueryDispatcher(store)).bots[0]

    restarts = (
        is_declared(state, BotLifecycleEvent.APP_RESTART)
        and next_target(state, BotLifecycleEvent.APP_RESTART)
        is BotLifecycleState.RECOVERING
    )
    assert entry.recovers_on_restart is restarts
    assert entry.payload()["recovers_on_restart"] is restarts


def test_a_running_a_paused_and_a_recovering_bot_are_the_ones_a_restart_recovers() -> (
    None
):
    """Pins the table's current answer, so a change to the restart rule is seen here too."""
    store = FakeBotStore()
    for index, state in enumerate(BotLifecycleState):
        seed(store, f"{index:06d}", state)

    recovers = {
        entry.state
        for entry in _report(BotQueryDispatcher(store)).bots
        if entry.recovers_on_restart
    }

    assert recovers == {"RUNNING", "PAUSED", "RECOVERING"}


def test_the_at_rest_states_are_the_lifecycles() -> None:
    """The report spells states as strings; the host decides what a stop leaves by
    them. The constant must say what the bots' close objection says."""
    assert {state.value for state in _AT_REST} == AT_REST_STATES
