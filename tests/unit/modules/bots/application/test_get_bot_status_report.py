"""`EPIC-038C` — the one bot status read model agrees with the Bots tab's own list."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    UNREADABLE_STATE,
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
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
