"""`EPIC-038I` - `bot export`, the applied-plan record on disk, and the plan the host reads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.file_applied_plan_store import (
    FileAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.applied_bot_plan import (
    AppliedBotPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_parser import (
    parse_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
    diff_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_export import (
    UnknownBotsError,
    export_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    AppliedPlanUnreadableError,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    MemoryAppliedPlanStore,
    StubKind,
    stored,
)

_SECRET = "SECRET-SENTINEL-6d2f81c4-never-print-me"  # noqa: S105 - a fake, planted to prove it is never printed


def _bots():
    return (
        stored("aaaaaa", BotLifecycleState.RUNNING, name="one"),
        stored(
            "bbbbbb",
            BotLifecycleState.STOPPED,
            name="two",
            venue=TradingVenue.SPOT_MAINNET,
        ),
        stored("cccccc", BotLifecycleState.HALTED, name="three"),
    )


def test_export_writes_every_bot_with_the_desire_its_state_implies() -> None:
    document = export_plan(_bots(), None, ())

    by_name = {bot.name: bot for bot in document.bots}
    assert by_name["one"].desired_state is DesiredState.RUNNING
    assert by_name["two"].desired_state is DesiredState.STOPPED
    assert by_name["three"].desired_state is DesiredState.STOPPED
    assert dict(by_name["one"].params) == {"lower": "60000", "upper": "70000"}


def test_export_prefers_what_the_record_says_the_operator_wants() -> None:
    recorded = AppliedPlan(
        (AppliedBot("bbbbbb", "two", "spot_mainnet", DesiredState.RUNNING),)
    )

    document = export_plan(_bots(), recorded, ())

    assert {b.name: b.desired_state for b in document.bots}[
        "two"
    ] is DesiredState.RUNNING


def test_export_of_named_ids_holds_only_those_and_refuses_an_unknown_id() -> None:
    document = export_plan(_bots(), None, ("bbbbbb",))

    assert [b.name for b in document.bots] == ["two"]
    with pytest.raises(UnknownBotsError, match="zzzzzz"):
        export_plan(_bots(), None, ("zzzzzz",))


def test_export_then_a_dry_run_is_no_changes() -> None:
    document = export_plan(_bots(), None, ())
    catalog = BotKindCatalog([StubKind("grid")])

    reread = parse_plan(document.to_json_text(), catalog)
    diff = diff_plan(reread, _bots(), None, PrunePolicy.PRUNE)

    assert reread == document, "the file round-trips"
    assert not diff.has_changes, [c.detail for c in diff.changes]


def test_an_exported_plan_and_its_diff_hold_no_secret_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_API_SECRET", _SECRET)
    monkeypatch.setenv("BINANCE_SPOT_TESTNET_API_KEY", "CANARY-KEY-" + _SECRET)
    document = export_plan(_bots(), None, ())
    diff = diff_plan(document, _bots(), None, PrunePolicy.KEEP)

    text = document.to_json_text() + "\n".join(c.detail for c in diff.changes)

    assert _SECRET not in text
    assert "api" not in text.lower().replace("apply", "")


# --- the record on disk ---------------------------------------------------------


def test_the_record_round_trips_through_its_file(tmp_path: Path) -> None:
    store = FileAppliedPlanStore(tmp_path / "state" / "bot_plan.json")
    plan = AppliedPlan(
        (
            AppliedBot("aaaaaa", "one", "spot_testnet", DesiredState.RUNNING),
            AppliedBot("bbbbbb", "two", "spot_mainnet", DesiredState.STOPPED),
        )
    )

    store.write(plan)

    assert store.read() == plan
    assert not list((tmp_path / "state").glob("*.tmp")), "the write left no temp file"


def test_no_record_is_none_not_an_error(tmp_path: Path) -> None:
    assert FileAppliedPlanStore(tmp_path / "bot_plan.json").read() is None


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "[]",
        '{"schema": "sew.bot-plan-record/9", "bots": []}',
        '{"schema": "sew.bot-plan-record/1", "bots": [{"bot_id": "aaaaaa"}]}',
        '{"schema": "sew.bot-plan-record/1", "bots": [{"bot_id": "aaaaaa", "name": "n", "venue": "v", "desired_state": "dancing"}]}',
        '{"schema": "sew.bot-plan-record/1", "bots": [], "api_key": "' + _SECRET + '"}',
    ],
    ids=[
        "not json",
        "not an object",
        "later schema",
        "missing fields",
        "bad state",
        "unknown field",
    ],
)
def test_a_record_that_cannot_be_read_is_refused_without_echoing_its_content(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "bot_plan.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(AppliedPlanUnreadableError) as raised:
        FileAppliedPlanStore(path).read()

    assert _SECRET not in str(raised.value)


def test_the_record_file_holds_ids_names_venues_and_states_only(tmp_path: Path) -> None:
    path = tmp_path / "bot_plan.json"
    FileAppliedPlanStore(path).write(
        AppliedPlan(
            (AppliedBot("aaaaaa", "one", "spot_testnet", DesiredState.RUNNING),)
        )
    )

    (bot,) = json.loads(path.read_text(encoding="utf-8"))["bots"]

    assert set(bot) == {"bot_id", "name", "venue", "desired_state"}


# --- the plan the host reads ----------------------------------------------------


def test_no_applied_plan_means_there_is_no_plan() -> None:
    plan = AppliedBotPlan(MemoryAppliedPlanStore(None))

    assert plan.exists() is False and plan.problem() is None
    assert plan.wants_running() == frozenset()


def test_the_host_starts_only_what_the_record_says_is_running() -> None:
    record = AppliedPlan(
        (
            AppliedBot("aaaaaa", "one", "spot_testnet", DesiredState.RUNNING),
            AppliedBot("bbbbbb", "two", "spot_testnet", DesiredState.STOPPED),
        )
    )
    plan = AppliedBotPlan(MemoryAppliedPlanStore(record))

    assert plan.exists() and plan.problem() is None
    assert plan.wants_running() == frozenset({"aaaaaa"})


def test_an_unreadable_record_is_a_problem_and_never_an_empty_plan() -> None:
    store = MemoryAppliedPlanStore()
    store.unreadable = True
    plan = AppliedBotPlan(store)

    assert plan.problem() is not None and "not JSON" in plan.problem()
    assert plan.exists() is True, "something is there; it must not read as 'no plan'"
    with pytest.raises(AppliedPlanUnreadableError):
        plan.wants_running()  # loud, never "nothing wanted"
