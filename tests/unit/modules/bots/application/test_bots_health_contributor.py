"""The bots' section of the health snapshot and the report's `app_running` (`EPIC-038C`)."""

from __future__ import annotations

import json

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bots_health_contributor import (
    BotsHealthContributor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
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
    BotQueryDispatcher,
)


class CountingProbe(IInstanceProbe):
    def __init__(self, held: bool) -> None:
        self.held = held
        self.asked = 0

    def is_held(self) -> bool:
        self.asked += 1
        return self.held


def _store() -> FakeBotStore:
    store = FakeBotStore()
    seed(store, "aaaaaa", BotLifecycleState.RUNNING)
    seed(store, "bbbbbb", BotLifecycleState.RUNNING)
    seed(store, "cccccc", BotLifecycleState.PAUSED)
    seed(store, "dddddd", BotLifecycleState.HALTED)
    seed(store, "eeeeee", BotLifecycleState.DRAFT)
    store.refuse_file(BotId("ffffff"), "not json")
    return store


def test_the_section_carries_the_health_lines_bot_counts() -> None:
    section = BotsHealthContributor(BotQueryDispatcher(_store())).snapshot()

    assert (
        section["total"],
        section["running"],
        section["paused"],
        section["halted"],
    ) == (
        5,
        2,
        1,
        1,
    )
    assert section["unreadable"] == 1
    assert section["states"] == {
        "RUNNING": 2,
        "PAUSED": 1,
        "HALTED": 1,
        "DRAFT": 1,
        "unreadable": 1,
    }


def test_the_section_holds_no_name_symbol_or_profit() -> None:
    text = json.dumps(
        dict(BotsHealthContributor(BotQueryDispatcher(_store())).snapshot())
    )

    assert "grid one" not in text
    assert "BTCUSDT" not in text
    assert "profit" not in text.lower()


def test_a_writable_copy_does_not_probe_its_own_lock() -> None:
    probe = CountingProbe(held=False)
    dispatcher = BotQueryDispatcher(_store(), probe, InstanceAccess.unguarded())

    report = dispatcher.dispatch(GetBotStatusReportQuery, GetBotStatusReportQuery())

    assert isinstance(report, BotStatusReport)
    assert report.app_running is True
    assert probe.asked == 0


def test_a_read_only_copy_asks_the_lock() -> None:
    for held in (True, False):
        probe = CountingProbe(held)
        dispatcher = BotQueryDispatcher(
            _store(), probe, InstanceAccess.declined("reads")
        )

        report = dispatcher.dispatch(GetBotStatusReportQuery, GetBotStatusReportQuery())

        assert isinstance(report, BotStatusReport)
        assert report.app_running is held
        assert probe.asked == 1


def test_an_unknown_state_of_the_world_is_not_running() -> None:
    assert BotStatusReport().app_running is False


def test_the_section_counts_the_bots_waiting_to_recover() -> None:
    """`EPIC-042B`: a bot waiting for its cause to clear is neither running nor halted."""
    store = FakeBotStore()
    seed(store, "aaaaaa", BotLifecycleState.AWAITING_RECOVERY)
    seed(store, "bbbbbb", BotLifecycleState.AWAITING_RECOVERY)
    seed(store, "cccccc", BotLifecycleState.HALTED)

    section = BotsHealthContributor(BotQueryDispatcher(store)).snapshot()

    assert (section["awaiting_recovery"], section["halted"], section["running"]) == (
        2,
        1,
        0,
    )


def test_the_section_counts_the_bots_waiting_for_their_range_apart_from_running() -> (
    None
):
    """`EPIC-044C`: a bot that holds nothing and waits for the price is not a running bot."""
    store = FakeBotStore()
    seed(store, "aaaaaa", BotLifecycleState.AWAITING_RANGE)
    seed(store, "bbbbbb", BotLifecycleState.RUNNING)

    section = BotsHealthContributor(BotQueryDispatcher(store)).snapshot()

    assert (section["awaiting_range"], section["running"]) == (1, 1)
