"""`EPIC-045C` - the applied record beside a host ends as an offline apply of the same plan leaves it.

A wish the plan gives no fresh row must go: a pruned bot whose delete the host refuses, a named entry the lifecycle
table blocks, and an `unplan` the host never answers (review of #717). Otherwise `run --start-planned` starts a bot the
operator just pruned, or one whose new parameters were never applied.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    DesiredState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    save_bot,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.bot_apply_host_world import (
    OLD,
    S,
    Setup,
    a_plan_file,
    an_entry,
    wishes_of,
)


def _stale_rows(setup: Setup) -> None:
    save_bot(setup.world.store, "aaaaaa", S.STOPPED, "kept", OLD)
    save_bot(setup.world.store, "cccccc", S.STOPPED, "retired", OLD)
    save_bot(setup.world.store, "dddddd", S.RUNNING, "busy", OLD)
    setup.plans.plan = AppliedPlan(
        (
            AppliedBot("aaaaaa", "kept", "spot_testnet", DesiredState.RUNNING),
            AppliedBot("cccccc", "retired", "spot_testnet", DesiredState.RUNNING),
            AppliedBot("dddddd", "busy", "spot_testnet", DesiredState.RUNNING),
        )
    )


def test_a_prune_delete_the_host_refuses_still_leaves_no_wish_for_the_bot(
    tmp_path: Path,
) -> None:
    """The offline apply writes no row for a bot the plan omits, whatever happens to its delete (review of #717)."""
    beside, offline = Setup(), Setup()
    for setup in (beside, offline):
        _stale_rows(setup)
    beside.host.refuse["cccccc"] = "exposure left: a live order"
    plan = a_plan_file(tmp_path, an_entry("kept"))

    beside.beside_a_host(plan, prune=True)
    offline.offline(plan, prune=True)

    assert "retired" in beside.names(), "the host kept the bot it refused to delete"
    assert (
        {w[0] for w in wishes_of(beside)}
        == {w[0] for w in wishes_of(offline)}
        == {"kept"}
    )


def test_a_named_entry_the_table_blocks_loses_its_old_wish_as_offline_does(
    tmp_path: Path,
) -> None:
    """Otherwise a later `run --start-planned` starts the bot on the parameters the plan wanted changed."""
    beside, offline = Setup(), Setup()
    for setup in (beside, offline):
        _stale_rows(setup)
    plan = a_plan_file(
        tmp_path, an_entry("kept"), an_entry("busy", lower="1", upper="2")
    )

    beside.beside_a_host(plan)
    offline.offline(plan)

    assert {w[0] for w in wishes_of(beside)} == {w[0] for w in wishes_of(offline)}
    assert "busy" not in {w[0] for w in wishes_of(beside)}


def test_a_host_gone_quiet_on_an_unplan_is_reported_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    setup = Setup()
    _stale_rows(setup)
    setup.host.answers_before_silence = 1

    outcome = setup.beside_a_host(a_plan_file(tmp_path, an_entry("kept")))

    document = json.loads(capsys.readouterr().out)["data"]
    notes = [n for n in document["notes"] if "not removed" in n]
    assert len(notes) == 2, "both stale wishes are named, the unanswered and the unsent"
    assert any("not sent" in n for n in notes)
    assert outcome is not None and outcome.code is ExitCode.HOST_UNHEALTHY
    assert "were not sent" in outcome.message
