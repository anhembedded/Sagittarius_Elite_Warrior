"""`EPIC-038I` - applying a plan drives the commands the screen uses, once, and records what it wants.

The handlers are the real ones over the verified in-memory store, so a refusal here is the
lifecycle table's, not a double's.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_applier import (
    PlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_change import (
    ChangeAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot.command import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot.command import (
    DeleteBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot.command import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.helpers import (
    seed,
    state_of,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    CommandWorld,
    MemoryAppliedPlanStore,
    planned,
)


def _applier(world: CommandWorld, store: MemoryAppliedPlanStore) -> PlanApplier:
    return PlanApplier(world, store)


def _apply(world, store, *entries, prune=PrunePolicy.KEEP):
    return _applier(world, store).apply(BotPlanDocument(tuple(entries)), prune)


def test_a_new_entry_is_created_through_the_create_command_and_recorded_with_its_id() -> (
    None
):
    world, store = CommandWorld(), MemoryAppliedPlanStore()

    result = _apply(world, store, planned())

    (command,) = world.commands()
    assert isinstance(command, CreateBotCommand)
    assert (command.name, command.kind, command.symbol) == (
        "BTC grid",
        "grid",
        "BTCUSDT",
    )
    assert dict(command.config) == {"lower": "60000", "upper": "70000"}
    (stored,) = world.store.load_all().bots
    assert stored.bot.state is BotLifecycleState.DRAFT, "applying starts nothing"
    assert store.plan is not None
    (recorded,) = store.plan.bots
    assert recorded.bot_id == stored.bot.bot_id.value
    assert recorded.desired_state is DesiredState.RUNNING
    assert result.exit_ok


def test_applying_twice_changes_nothing_the_second_time() -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    _apply(world, store, planned(), planned("second", desired=DesiredState.STOPPED))
    commands_after_first = len(world.commands())
    writes_after_first = store.writes

    second = _apply(
        world, store, planned(), planned("second", desired=DesiredState.STOPPED)
    )

    assert not second.diff.has_changes
    assert len(world.commands()) == commands_after_first, "no command was dispatched"
    assert store.writes == writes_after_first, "the record was not rewritten"
    assert len(world.store.load_all().bots) == 2, "no duplicate bot"


def test_a_changed_parameter_edits_a_stopped_bot_through_the_edit_command() -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    seed(world.store, "aaaaaa", BotLifecycleState.STOPPED, {"lower": "1", "upper": "2"})

    _apply(world, store, planned(name="grid one", params={"lower": "5", "upper": "9"}))

    (command,) = world.commands()
    assert isinstance(command, EditBotCommand) and command.bot_id == "aaaaaa"
    stored = world.store.load_all().bots[0].bot
    assert dict(stored.definition.config) == {"lower": "5", "upper": "9"}
    assert stored.state is BotLifecycleState.DRAFT


def test_a_running_bots_range_edit_is_refused_by_the_table_and_the_other_entries_still_apply() -> (
    None
):
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    seed(world.store, "aaaaaa", BotLifecycleState.RUNNING, {"lower": "1", "upper": "2"})

    result = _apply(
        world,
        store,
        planned(name="grid one", params={"lower": "5", "upper": "9"}),
        planned("fresh one"),
    )

    assert not result.exit_ok
    actions = {o.change.name: o for o in result.outcomes}
    assert actions["grid one"].change.action is ChangeAction.BLOCKED
    assert "stop" in actions["grid one"].message.lower()
    assert actions["fresh one"].done, "each bot is applied independently"
    assert state_of(world.store, "aaaaaa") is BotLifecycleState.RUNNING
    assert dict(world.store.load_all().bots[0].bot.definition.config) == {
        "lower": "1",
        "upper": "2",
    }, "nothing half-applied"
    assert store.plan is not None
    assert "aaaaaa" not in {b.bot_id for b in store.plan.bots}, (
        "a blocked entry is not recorded: --start-planned must not start params the operator did not get"
    )


def test_prune_deletes_a_stopped_bot_the_plan_does_not_name_through_the_delete_command() -> (
    None
):
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    seed(world.store, "aaaaaa", BotLifecycleState.STOPPED)

    _apply(world, store, prune=PrunePolicy.PRUNE)

    (command,) = world.commands()
    assert isinstance(command, DeleteBotCommand) and command.bot_id == "aaaaaa"
    assert world.store.load_all().bots == ()


def test_prune_leaves_a_running_bot_and_says_it_needs_a_stop() -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    seed(world.store, "aaaaaa", BotLifecycleState.RUNNING)

    result = _apply(world, store, prune=PrunePolicy.PRUNE)

    assert world.commands() == []
    assert not result.exit_ok
    assert state_of(world.store, "aaaaaa") is BotLifecycleState.RUNNING


def test_without_prune_an_unnamed_bot_is_neither_deleted_nor_recorded() -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    seed(world.store, "aaaaaa", BotLifecycleState.STOPPED)

    result = _apply(world, store)

    assert world.commands() == [] and result.exit_ok
    assert store.plan is None or store.plan.bots == ()


def test_a_dry_run_dispatches_nothing_and_writes_nothing() -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    seed(world.store, "aaaaaa", BotLifecycleState.STOPPED, {"lower": "1", "upper": "2"})

    diff = _applier(world, store).diff(
        BotPlanDocument(
            (
                planned(name="grid one", params={"lower": "5", "upper": "9"}),
                planned("new"),
            )
        ),
        PrunePolicy.PRUNE,
    )

    assert diff.has_changes
    assert world.commands() == [] and store.writes == 0


def test_a_desired_state_change_alone_rewrites_the_record_and_nothing_else() -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    seed(
        world.store,
        "aaaaaa",
        BotLifecycleState.STOPPED,
        {"lower": "60000", "upper": "70000"},
    )
    store.plan = AppliedPlan(
        (AppliedBot("aaaaaa", "grid one", "spot_testnet", DesiredState.STOPPED),)
    )

    result = _apply(
        world, store, planned(name="grid one", desired=DesiredState.RUNNING)
    )

    assert world.commands() == []
    assert result.diff.has_changes
    assert store.plan.desired_for("aaaaaa") is DesiredState.RUNNING


def test_an_unreadable_record_is_replaced_and_the_result_says_so() -> None:
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    store.unreadable = True

    result = _apply(world, store, planned())

    assert any("record" in n and "replaced" in n for n in result.notes), result.notes
    assert store.plan is not None and len(store.plan.bots) == 1


def test_an_apply_logs_one_summary_line_with_the_counts(caplog) -> None:  # type: ignore[no-untyped-def]
    world, store = CommandWorld(), MemoryAppliedPlanStore()
    seed(world.store, "aaaaaa", BotLifecycleState.RUNNING, {"lower": "1", "upper": "2"})

    with caplog.at_level(logging.INFO, logger="App.Bots.Plan"):
        _apply(world, store, planned(name="grid one"), planned("fresh one"))

    (line,) = [r.getMessage() for r in caplog.records if r.name == "App.Bots.Plan"]
    assert line.startswith("[plan] applied")
    assert "1 create" in line and "1 blocked" in line
