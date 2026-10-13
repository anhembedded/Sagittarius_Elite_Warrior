"""`EPIC-038I` - what applying a plan would do, decided by the lifecycle table, not by a list here."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
    PlannedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_change import (
    ChangeAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
    diff_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    AT_REST_STATES,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
    permits_delete,
    permits_edit,
    restarts_into_recovering,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    planned,
    stored,
)


def diff(
    plan: tuple[PlannedBot, ...],
    bots: tuple[BotSnapshot, ...] = (),
    recorded: AppliedPlan | None = None,
    prune: PrunePolicy = PrunePolicy.KEEP,
):
    return diff_plan(BotPlanDocument(plan), bots, recorded, prune)


def only(changes) -> object:
    (change,) = changes.changes
    return change


def test_an_entry_with_no_bot_is_created() -> None:
    change = only(diff((planned(),)))

    assert change.action is ChangeAction.CREATE
    assert change.is_change
    assert "start-planned" in change.detail, (
        "the diff says what desired_state will mean"
    )


def test_an_entry_that_matches_its_bot_is_left_and_the_diff_has_no_changes() -> None:
    recorded = AppliedPlan(
        (AppliedBot("aaaaaa", "BTC grid", "spot_testnet", DesiredState.RUNNING),)
    )

    result = diff((planned(),), (stored("aaaaaa"),), recorded)

    assert only(result).action is ChangeAction.LEAVE
    assert not result.has_changes


@pytest.mark.parametrize("state", list(BotLifecycleState), ids=lambda s: s.value)
def test_a_changed_parameter_is_an_edit_only_where_the_lifecycle_table_permits_it(
    state: BotLifecycleState,
) -> None:
    changed = planned(params={"lower": "61000", "upper": "70000"})

    change = only(diff((changed,), (stored("aaaaaa", state),)))

    expected = ChangeAction.EDIT if permits_edit(state) else ChangeAction.BLOCKED
    assert change.action is expected
    if expected is ChangeAction.BLOCKED:
        assert "stop" in change.detail.lower() and state.value in change.detail


def test_the_lifecycle_tables_answer_is_draft_and_stopped_only() -> None:
    """Pins the table's current answer, so a change to it is seen here as well."""
    editable = {s for s in BotLifecycleState if permits_edit(s)}
    deletable = {s for s in BotLifecycleState if permits_delete(s)}

    assert editable == deletable == {BotLifecycleState.DRAFT, BotLifecycleState.STOPPED}


@pytest.mark.parametrize(
    "different",
    [{"kind": "dca"}, {"symbol": "ETHUSDT"}],
    ids=["kind", "symbol"],
)
def test_a_kind_or_symbol_cannot_be_edited_in_place(different: dict[str, str]) -> None:
    change = only(diff((planned(**different),), (stored("aaaaaa"),)))

    assert change.action is ChangeAction.BLOCKED
    assert "new bot" in change.detail or "cannot be edited" in change.detail


def test_two_stored_bots_with_one_name_and_venue_block_the_entry_and_name_both() -> (
    None
):
    bots = (stored("aaaaaa"), stored("bbbbbb"))

    change = only(diff((planned(),), bots))

    assert change.action is ChangeAction.BLOCKED
    assert "aaaaaa" in change.detail and "bbbbbb" in change.detail


def test_the_same_name_on_another_venue_is_another_bot() -> None:
    result = diff(
        (planned(venue=TradingVenue.SPOT_MAINNET),),
        (stored("aaaaaa", venue=TradingVenue.SPOT_TESTNET),),
    )

    assert [c.action for c in result.changes] == [
        ChangeAction.CREATE,
        ChangeAction.LEAVE,
    ]
    assert result.changes[1].bot_id == "aaaaaa", (
        "the testnet bot is another bot, left alone"
    )


def test_a_bot_the_plan_does_not_name_is_kept_unless_pruned() -> None:
    kept = only(diff((), (stored("aaaaaa"),)))

    assert kept.action is ChangeAction.LEAVE and not kept.is_change
    assert "--prune" in kept.detail


@pytest.mark.parametrize("state", list(BotLifecycleState), ids=lambda s: s.value)
def test_prune_deletes_only_a_bot_at_rest(state: BotLifecycleState) -> None:
    change = only(diff((), (stored("aaaaaa", state),), prune=PrunePolicy.PRUNE))

    expected = ChangeAction.DELETE if permits_delete(state) else ChangeAction.BLOCKED
    assert change.action is expected
    assert "rename" in change.detail.lower() or expected is ChangeAction.BLOCKED


def test_a_rename_is_a_delete_and_a_create_and_the_diff_says_so() -> None:
    result = diff(
        (planned(name="BTC grid v2"),),
        (stored("aaaaaa", name="BTC grid"),),
        prune=PrunePolicy.PRUNE,
    )

    actions = {c.name: c for c in result.changes}
    assert actions["BTC grid v2"].action is ChangeAction.CREATE
    assert actions["BTC grid"].action is ChangeAction.DELETE
    assert "rename" in actions["BTC grid"].detail.lower()


@pytest.mark.parametrize(
    ("desired", "state", "needle"),
    [
        (DesiredState.RUNNING, BotLifecycleState.STOPPED, "start-planned"),
        (DesiredState.RUNNING, BotLifecycleState.RUNNING, "already"),
        (DesiredState.STOPPED, BotLifecycleState.RUNNING, "does not stop"),
        (DesiredState.STOPPED, BotLifecycleState.STOPPED, "leaves it"),
    ],
)
def test_the_diff_says_what_desired_state_means_for_the_bot_as_it_is(
    desired: DesiredState, state: BotLifecycleState, needle: str
) -> None:
    recorded = AppliedPlan((AppliedBot("aaaaaa", "BTC grid", "spot_testnet", desired),))

    change = only(
        diff((planned(desired=desired),), (stored("aaaaaa", state),), recorded)
    )

    assert needle in change.detail


def test_a_changed_desired_state_alone_is_a_change_to_the_record() -> None:
    recorded = AppliedPlan(
        (AppliedBot("aaaaaa", "BTC grid", "spot_testnet", DesiredState.STOPPED),)
    )

    result = diff(
        (planned(desired=DesiredState.RUNNING),), (stored("aaaaaa"),), recorded
    )

    change = only(result)
    assert change.action is ChangeAction.LEAVE
    assert change.desired_before is DesiredState.STOPPED
    assert change.desired_after is DesiredState.RUNNING
    assert change.is_change and result.has_changes


def test_with_no_record_the_desired_state_before_is_what_the_bots_state_implies() -> (
    None
):
    """So `export` then `apply --dry-run` finds no change: an exported RUNNING bot says running."""
    running = stored("aaaaaa", BotLifecycleState.RUNNING)
    stopped = stored("bbbbbb", BotLifecycleState.STOPPED, name="other")

    result = diff(
        (
            planned(desired=DesiredState.RUNNING),
            planned("other", desired=DesiredState.STOPPED),
        ),
        (running, stopped),
        None,
    )

    assert not result.has_changes, [c.detail for c in result.changes]


def test_blocked_entries_are_reported_and_do_not_hide_the_others() -> None:
    plan = (
        planned(params={"lower": "1", "upper": "2"}),
        planned("new one", desired=DesiredState.STOPPED),
    )

    result = diff(plan, (stored("aaaaaa", BotLifecycleState.RUNNING),))

    assert [c.action for c in result.changes] == [
        ChangeAction.BLOCKED,
        ChangeAction.CREATE,
    ]
    assert result.blocked


@pytest.mark.parametrize("state", list(BotLifecycleState), ids=lambda s: s.value)
def test_the_diff_promises_a_start_only_for_a_bot_the_host_would_start(
    state: BotLifecycleState,
) -> None:
    """`run --start-planned` starts a bot that is *at rest*: the report's `AT_REST_STATES`,
    the rule the host asks. HALTED, ERROR and STOPPING are not at rest and are not started."""
    recorded = AppliedPlan(
        (AppliedBot("aaaaaa", "BTC grid", "spot_testnet", DesiredState.RUNNING),)
    )

    change = only(diff((planned(),), (stored("aaaaaa", state),), recorded))

    starts = "will start it" in change.detail
    assert starts is (state.value in AT_REST_STATES), (state, change.detail)
    if not starts and not restarts_into_recovering(state):
        assert "will not start" in change.detail and state.value in change.detail


def test_a_new_bot_and_an_edited_one_are_drafts_so_the_host_will_start_them() -> None:
    created = only(diff((planned(),)))
    edited = only(
        diff(
            (planned(params={"lower": "1", "upper": "2"}),),
            (stored("aaaaaa", BotLifecycleState.STOPPED),),
        )
    )

    assert "will start it" in created.detail and "will start it" in edited.detail
