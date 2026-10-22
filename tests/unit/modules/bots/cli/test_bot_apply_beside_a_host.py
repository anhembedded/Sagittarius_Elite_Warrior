"""`EPIC-045C` - `bot apply` beside a running host: the same plan, carried out entry by entry through the host.

The host here is `InProcessHost`: the operator's requests reach the host's real handlers over an in-memory store and
applied-plan record, so what these tests assert is what a host would do (decision C6).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlReply,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_plan_verbs import (
    ApplyBotPlanVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    DesiredState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    save_bot,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.bot_apply_host_world import (
    OLD,
    PRINTER,
    SECOND_COPY,
    S,
    Setup,
    a_plan_file,
    an_entry,
    verb_args,
    wishes_of,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.verb_world import (
    RecordingHostControl,
    verb_world,
)


def _mixed_plan(tmp_path: Path) -> Path:
    return a_plan_file(
        tmp_path,
        an_entry("edited", "running", lower="61000", upper="70000"),
        an_entry("same", "running"),
        an_entry("fresh", "running"),
    )


def test_a_plan_is_carried_out_entry_by_entry_and_the_record_is_the_one_an_offline_apply_leaves(
    tmp_path: Path,
) -> None:
    beside, offline = Setup(), Setup()
    for setup in (beside, offline):
        setup.seed()
    plan = _mixed_plan(tmp_path)

    outcome = beside.beside_a_host(plan, prune=True)
    expected = offline.offline(plan, prune=True)

    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert "need attention" in outcome.message, (
        "the RUNNING bot the plan does not name is blocked from prune"
    )
    assert expected is not None and expected.code is ExitCode.USAGE
    assert beside.names() == offline.names()
    assert wishes_of(beside) == wishes_of(offline), (
        "ids of created bots differ; the wishes may not"
    )
    assert "retired" not in beside.names() and "busy" in beside.names()


def test_the_requests_are_the_plans_entries_first_the_forgotten_wishes_then_the_deletes(
    tmp_path: Path,
) -> None:
    setup = Setup()
    setup.seed()

    setup.beside_a_host(_mixed_plan(tmp_path), prune=True)

    sent = [(r.action, r.entry.name if r.entry else r.bot_id) for r in setup.host.sent]
    assert sent == [
        (HostControlAction.APPLY_ENTRY, "edited"),
        (HostControlAction.APPLY_ENTRY, "same"),
        (HostControlAction.APPLY_ENTRY, "fresh"),
        (HostControlAction.UNPLAN, "cccccc"),
        (HostControlAction.UNPLAN, "dddddd"),
        (HostControlAction.DELETE, "cccccc"),
    ]
    assert all(r.confirmed_venue is None for r in setup.host.sent), (
        "applying asks no venue and starts nothing"
    )


def test_a_created_bot_is_a_draft_and_nothing_is_started(tmp_path: Path) -> None:
    setup = Setup()

    outcome = setup.beside_a_host(a_plan_file(tmp_path, an_entry("fresh")))

    assert outcome is None
    (stored,) = setup.world.store.load_all().bots
    assert stored.bot.state is S.DRAFT
    assert setup.plans.plan is not None
    assert setup.plans.plan.desired_for(stored.bot.bot_id.value) is DesiredState.RUNNING


def test_an_entry_the_table_blocks_is_not_sent_and_the_others_are_applied(
    tmp_path: Path,
) -> None:
    setup = Setup()
    save_bot(setup.world.store, "dddddd", S.RUNNING, "busy", OLD)
    plan = a_plan_file(
        tmp_path, an_entry("busy", "running", lower="1", upper="2"), an_entry("fresh")
    )

    outcome = setup.beside_a_host(plan)

    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert [r.entry.name for r in setup.host.sent if r.entry] == ["fresh"]
    assert setup.names()["busy"] == OLD, "a bot that needs a stop first is untouched"


def test_an_entry_the_host_refuses_does_not_stop_the_others_and_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    setup = Setup()
    setup.host.refuse["first"] = "the host would not"
    plan = a_plan_file(tmp_path, an_entry("first"), an_entry("second"))

    outcome = setup.beside_a_host(plan)

    document = json.loads(capsys.readouterr().out)["data"]
    done = {c["name"]: c["done"] for c in document["changes"]}
    assert done == {"first": False, "second": True}
    assert any("the host would not" in note for note in document["notes"])
    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert "first on spot_testnet" in outcome.message
    assert "second" in setup.names() and "first" not in setup.names()


def test_a_host_that_stops_answering_leaves_the_rest_listed_as_not_sent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    setup = Setup()
    setup.host.answers_before_silence = 1
    plan = a_plan_file(tmp_path, an_entry("one"), an_entry("two"), an_entry("three"))

    outcome = setup.beside_a_host(plan)

    document = json.loads(capsys.readouterr().out)["data"]
    done = {c["name"]: c["done"] for c in document["changes"]}
    assert done == {"one": True, "two": False, "three": False}
    assert any(
        n.startswith("two on spot_testnet: sent, outcome unknown")
        for n in document["notes"]
    ), "a taken command with no outcome may have run"
    assert any(
        n.startswith("three on spot_testnet: not sent") for n in document["notes"]
    )
    assert outcome is not None and outcome.code is ExitCode.HOST_UNHEALTHY
    assert (
        "1 change(s) were not sent and 1 were sent with the outcome unknown"
        in outcome.message
    )
    assert len(setup.host.sent) == 2, "nothing is sent to a host that has gone quiet"
    assert list(setup.names()) == ["one"]


def test_no_host_to_answer_the_first_command_is_exit_ten_with_nothing_changed(
    tmp_path: Path,
) -> None:
    setup = Setup()
    setup.host.answers_before_silence = 0
    nobody = HostControlReply(HostControlStatus.NOT_RUNNING, "no host is running")
    setup.host.send = lambda request, wait: nobody  # type: ignore[method-assign]

    outcome = setup.beside_a_host(a_plan_file(tmp_path, an_entry("fresh")))

    assert outcome is not None and outcome.code is ExitCode.HOST_NOT_RUNNING
    assert "no host is running" in outcome.message
    assert setup.names() == {} and setup.plans.writes == 0


def test_a_plan_with_an_entry_no_command_file_can_carry_sends_nothing(
    tmp_path: Path,
) -> None:
    setup = Setup()
    too_many = {f"p{i}": "1" for i in range(40)}
    plan = a_plan_file(tmp_path, an_entry("fine"), an_entry("wide", **too_many))

    outcome = setup.beside_a_host(plan)

    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert (
        "wide on spot_testnet" in outcome.message
        and "nothing was sent" in outcome.message
    )
    assert setup.host.sent == [] and setup.names() == {}


def test_applying_the_same_plan_again_beside_a_host_changes_nothing(
    tmp_path: Path,
) -> None:
    setup = Setup()
    plan = a_plan_file(tmp_path, an_entry("fresh"))
    setup.beside_a_host(plan)
    after_first = (setup.names(), setup.plans.plan, setup.plans.writes)

    setup.beside_a_host(plan)

    assert (setup.names(), setup.plans.plan, setup.plans.writes) == after_first


def test_a_plan_that_omits_a_bot_forgets_its_wish_and_leaves_the_bot(
    tmp_path: Path,
) -> None:
    setup = Setup()
    setup.seed()

    setup.beside_a_host(a_plan_file(tmp_path, an_entry("same")))

    assert setup.plans.plan is not None
    assert {row.bot_id for row in setup.plans.plan.bots} == {"bbbbbb"}
    assert set(setup.names()) == {"edited", "same", "retired", "busy"}, (
        "no prune: nothing is deleted"
    )


def test_a_dry_run_beside_a_host_sends_nothing(tmp_path: Path) -> None:
    setup = Setup()

    setup.beside_a_host(a_plan_file(tmp_path, an_entry("fresh")), dry_run=True)

    assert setup.host.sent == [] and setup.names() == {}


def test_a_copy_that_offers_no_control_is_exit_five_and_nothing_else_is_tried(
    tmp_path: Path,
) -> None:
    """Another copy holds the data root but takes no command (the desktop app, a host with no control)."""
    setup = Setup()
    nobody = RecordingHostControl(
        HostControlReply(
            HostControlStatus.NO_CONTROL, "the running copy offers no control"
        )
    )

    outcome = ApplyBotPlanVerb().run(
        verb_args(a_plan_file(tmp_path, an_entry("a"), an_entry("b"))),
        verb_world(
            setup.world,
            PRINTER,
            plans=setup.plans,
            instance=SECOND_COPY,
            host_control=nobody,
        ),
    )

    assert outcome is not None and outcome.code is ExitCode.CONFIGURATION
    assert "offers no control" in outcome.message
    assert len(nobody.sent) == 1, (
        "the first command found nobody, so no other was tried"
    )
    assert setup.names() == {} and setup.plans.writes == 0
