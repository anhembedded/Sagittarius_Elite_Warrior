"""`BOT-176` - `ExportBotPlanQuery`: the one place a plan document is assembled for `bot export` and the desktop."""

from __future__ import annotations

from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_export import (
    UnknownBotsError,
    export_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    ExportBotPlanQuery,
    ExportBotPlanQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    CommandWorld,
    MemoryAppliedPlanStore,
    save_bot,
)


def _world() -> tuple[CommandWorld, MemoryAppliedPlanStore]:
    world = CommandWorld()
    save_bot(world.store, "aaaaaa", BotLifecycleState.RUNNING, "one", {"lower": "1"})
    save_bot(
        world.store,
        "bbbbbb",
        BotLifecycleState.STOPPED,
        "two",
        {"lower": "3"},
        TradingVenue.SPOT_MAINNET,
    )
    return world, MemoryAppliedPlanStore()


def _handler(
    world: CommandWorld, store: MemoryAppliedPlanStore
) -> ExportBotPlanQueryHandler:
    return ExportBotPlanQueryHandler(world, store)


def test_the_document_is_what_export_plan_makes_of_the_stored_bots() -> None:
    world, store = _world()
    listing = world.dispatch(ListBotsQuery, ListBotsQuery())

    document = _handler(world, store).execute(ExportBotPlanQuery())

    assert document == export_plan(listing.bots, None, ())  # type: ignore[attr-defined]
    assert {bot.name: bot.desired_state for bot in document.bots} == {
        "one": DesiredState.RUNNING,
        "two": DesiredState.STOPPED,
    }


def test_ids_choose_the_bots_and_an_unknown_id_names_nothing() -> None:
    world, store = _world()
    handler = _handler(world, store)

    (only,) = handler.execute(ExportBotPlanQuery(("bbbbbb",))).bots

    assert only.name == "two"
    with pytest.raises(UnknownBotsError):
        handler.execute(ExportBotPlanQuery(("bbbbbb", "zzzzzz")))


def test_all_stopped_changes_only_the_desired_state() -> None:
    world, store = _world()
    handler = _handler(world, store)

    kept = handler.execute(ExportBotPlanQuery())
    stopped = handler.execute(ExportBotPlanQuery(all_stopped=True))

    assert [bot.desired_state for bot in stopped.bots] == [DesiredState.STOPPED] * 2
    assert stopped.bots == tuple(
        replace(bot, desired_state=DesiredState.STOPPED) for bot in kept.bots
    )
    assert any(bot.desired_state is DesiredState.RUNNING for bot in kept.bots)


def test_all_stopped_overrides_a_record_that_wants_a_bot_running() -> None:
    world, store = _world()
    store.plan = AppliedPlan(
        (AppliedBot("bbbbbb", "two", "spot_mainnet", DesiredState.RUNNING),)
    )
    handler = _handler(world, store)

    kept = handler.execute(ExportBotPlanQuery(("bbbbbb",)))
    stopped = handler.execute(ExportBotPlanQuery(("bbbbbb",), all_stopped=True))

    assert kept.bots[0].desired_state is DesiredState.RUNNING
    assert stopped.bots[0].desired_state is DesiredState.STOPPED


def test_an_unreadable_record_counts_as_none() -> None:
    world, store = _world()
    store.unreadable = True

    document = _handler(world, store).execute(ExportBotPlanQuery())

    assert {bot.name: bot.desired_state for bot in document.bots} == {
        "one": DesiredState.RUNNING,
        "two": DesiredState.STOPPED,
    }
