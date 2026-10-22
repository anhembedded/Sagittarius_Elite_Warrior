"""`EPIC-045C` - `bot apply` beside a running host: the same plan, carried out entry by entry through the host.

The host here is `InProcessHost`: the operator's requests reach the host's real handlers over an in-memory store and
applied-plan record, so what these tests assert is what a host would do, and the record they compare is the one an offline
apply writes for the same plan (decision C6).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import ExitCode
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlReply,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_plan_verbs import (
    ApplyBotPlanVerb,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    AppliedPlan,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.shell.report_printer import ReportPrinter
from Sagittarius_Elite_Warrior.src.support.cli_host.report_formats import ReportFormats
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_host_world import (
    InProcessHost,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    CommandWorld,
    MemoryAppliedPlanStore,
    save_bot,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.cli.verb_world import (
    RecordingHostControl,
    verb_world,
)

S = BotLifecycleState
_PRINTER = ReportPrinter(ReportFormats.default())
_SECOND_COPY = InstanceAccess.declined("Another copy holds the data root.")
_OLD = {"lower": "60000", "upper": "70000"}


def _entry(name: str, desired: str = "running", **params: str) -> dict[str, object]:
    return {
        "name": name,
        "kind": "grid",
        "venue": "spot_testnet",
        "symbol": "BTCUSDT",
        "params": params or _OLD,
        "desired_state": desired,
    }


def _plan(tmp_path: Path, *entries: dict[str, object]) -> Path:
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps({"schema": "sew.bot-plan/1", "bots": list(entries)}),
        encoding="utf-8",
    )
    return path


def _args(path: Path, **values: object) -> argparse.Namespace:
    return argparse.Namespace(
        **{
            "plan": str(path),
            "dry_run": False,
            "prune": False,
            "wait": 15.0,
            "json": True,
            "format": None,
            **values,
        }
    )


class _Setup:
    """One store and record; applied once beside a host and (in a twin) offline, to compare."""

    def __init__(self) -> None:
        self.world = CommandWorld()
        self.plans = MemoryAppliedPlanStore()
        self.host = InProcessHost(self.world, self.plans)

    def beside_a_host(self, path: Path, **values: object):
        return ApplyBotPlanVerb().run(
            _args(path, **values),
            verb_world(
                self.world,
                _PRINTER,
                plans=self.plans,
                instance=_SECOND_COPY,
                host_control=self.host,
            ),
        )

    def offline(self, path: Path, **values: object):
        return ApplyBotPlanVerb().run(
            _args(path, **values),
            verb_world(self.world, _PRINTER, plans=self.plans),
        )

    def seed(self) -> None:
        save_bot(self.world.store, "aaaaaa", S.STOPPED, "edited", _OLD)
        save_bot(self.world.store, "bbbbbb", S.STOPPED, "same", _OLD)
        save_bot(self.world.store, "cccccc", S.STOPPED, "retired", _OLD)
        save_bot(self.world.store, "dddddd", S.RUNNING, "busy", _OLD)
        self.plans.plan = AppliedPlan(
            (
                AppliedBot("aaaaaa", "edited", "spot_testnet", DesiredState.STOPPED),
                AppliedBot("cccccc", "retired", "spot_testnet", DesiredState.RUNNING),
                AppliedBot("dddddd", "busy", "spot_testnet", DesiredState.RUNNING),
            )
        )

    def names(self) -> dict[str, dict[str, str]]:
        return {
            stored.bot.definition.name: dict(stored.bot.definition.config)
            for stored in self.world.store.load_all().bots
        }


def _wishes(setup: _Setup) -> set[tuple[str, str, DesiredState]]:
    assert setup.plans.plan is not None
    return {(row.name, row.venue, row.desired_state) for row in setup.plans.plan.bots}


def _mixed_plan(tmp_path: Path) -> Path:
    return _plan(
        tmp_path,
        _entry("edited", "running", lower="61000", upper="70000"),
        _entry("same", "running"),
        _entry("fresh", "running"),
    )


def test_a_plan_is_carried_out_entry_by_entry_and_the_record_is_the_one_an_offline_apply_leaves(
    tmp_path: Path,
) -> None:
    beside, offline = _Setup(), _Setup()
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
    assert _wishes(beside) == _wishes(offline), (
        "ids of created bots differ; the wishes may not"
    )
    assert "retired" not in beside.names() and "busy" in beside.names()


def test_the_requests_are_the_plans_entries_first_the_forgotten_wishes_then_the_deletes(
    tmp_path: Path,
) -> None:
    setup = _Setup()
    setup.seed()

    setup.beside_a_host(_mixed_plan(tmp_path), prune=True)

    sent = [(r.action, r.entry.name if r.entry else r.bot_id) for r in setup.host.sent]
    assert sent == [
        (HostControlAction.APPLY_ENTRY, "edited"),
        (HostControlAction.APPLY_ENTRY, "same"),
        (HostControlAction.APPLY_ENTRY, "fresh"),
        (HostControlAction.UNPLAN, "dddddd"),
        (HostControlAction.DELETE, "cccccc"),
    ]
    assert all(r.confirmed_venue is None for r in setup.host.sent), (
        "applying asks no venue and starts nothing"
    )


def test_a_created_bot_is_a_draft_and_nothing_is_started(tmp_path: Path) -> None:
    setup = _Setup()

    outcome = setup.beside_a_host(_plan(tmp_path, _entry("fresh")))

    assert outcome is None
    (stored,) = setup.world.store.load_all().bots
    assert stored.bot.state is S.DRAFT
    assert setup.plans.plan is not None
    assert setup.plans.plan.desired_for(stored.bot.bot_id.value) is DesiredState.RUNNING


def test_an_entry_the_table_blocks_is_not_sent_and_the_others_are_applied(
    tmp_path: Path,
) -> None:
    setup = _Setup()
    save_bot(setup.world.store, "dddddd", S.RUNNING, "busy", _OLD)
    plan = _plan(
        tmp_path, _entry("busy", "running", lower="1", upper="2"), _entry("fresh")
    )

    outcome = setup.beside_a_host(plan)

    assert outcome is not None and outcome.code is ExitCode.USAGE
    assert [r.entry.name for r in setup.host.sent if r.entry] == ["fresh"]
    assert setup.names()["busy"] == _OLD, "a bot that needs a stop first is untouched"


def test_an_entry_the_host_refuses_does_not_stop_the_others_and_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    setup = _Setup()
    setup.host.refuse["first"] = "the host would not"
    plan = _plan(tmp_path, _entry("first"), _entry("second"))

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
    setup = _Setup()
    setup.host.answers_before_silence = 1
    plan = _plan(tmp_path, _entry("one"), _entry("two"), _entry("three"))

    outcome = setup.beside_a_host(plan)

    document = json.loads(capsys.readouterr().out)["data"]
    done = {c["name"]: c["done"] for c in document["changes"]}
    assert done == {"one": True, "two": False, "three": False}
    assert any("not sent" in note for note in document["notes"])
    assert outcome is not None and outcome.code is ExitCode.HOST_UNHEALTHY
    assert "2 change(s) were not sent" in outcome.message
    assert len(setup.host.sent) == 2, "nothing is sent to a host that has gone quiet"
    assert list(setup.names()) == ["one"]


def test_no_host_to_answer_the_first_command_is_the_old_exit_three_with_nothing_changed(
    tmp_path: Path,
) -> None:
    setup = _Setup()
    setup.host.answers_before_silence = 0
    nobody = HostControlReply(HostControlStatus.NOT_RUNNING, "no host is running")
    setup.host.send = lambda request, wait: nobody  # type: ignore[method-assign]

    outcome = setup.beside_a_host(_plan(tmp_path, _entry("fresh")))

    assert outcome is not None and outcome.code is ExitCode.LOCK_HELD
    assert "no host is running" in outcome.message
    assert setup.names() == {} and setup.plans.writes == 0


def test_a_plan_with_an_entry_no_command_file_can_carry_sends_nothing(
    tmp_path: Path,
) -> None:
    setup = _Setup()
    too_many = {f"p{i}": "1" for i in range(40)}
    plan = _plan(tmp_path, _entry("fine"), _entry("wide", **too_many))

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
    setup = _Setup()
    plan = _plan(tmp_path, _entry("fresh"))
    setup.beside_a_host(plan)
    after_first = (setup.names(), setup.plans.plan, setup.plans.writes)

    setup.beside_a_host(plan)

    assert (setup.names(), setup.plans.plan, setup.plans.writes) == after_first


def test_a_plan_that_omits_a_bot_forgets_its_wish_and_leaves_the_bot(
    tmp_path: Path,
) -> None:
    setup = _Setup()
    setup.seed()

    setup.beside_a_host(_plan(tmp_path, _entry("same")))

    assert setup.plans.plan is not None
    assert {row.bot_id for row in setup.plans.plan.bots} == {"bbbbbb"}
    assert set(setup.names()) == {"edited", "same", "retired", "busy"}, (
        "no prune: nothing is deleted"
    )


def test_a_dry_run_beside_a_host_sends_nothing(tmp_path: Path) -> None:
    setup = _Setup()

    setup.beside_a_host(_plan(tmp_path, _entry("fresh")), dry_run=True)

    assert setup.host.sent == [] and setup.names() == {}


def test_a_copy_that_offers_no_control_is_exit_three_and_nothing_else_is_tried(
    tmp_path: Path,
) -> None:
    """Another copy holds the data root but takes no command (the desktop app, a host with no control)."""
    setup = _Setup()
    nobody = RecordingHostControl(
        HostControlReply(
            HostControlStatus.NO_CONTROL, "the running copy offers no control"
        )
    )

    outcome = ApplyBotPlanVerb().run(
        _args(_plan(tmp_path, _entry("a"), _entry("b"))),
        verb_world(
            setup.world,
            _PRINTER,
            plans=setup.plans,
            instance=_SECOND_COPY,
            host_control=nobody,
        ),
    )

    assert outcome is not None and outcome.code is ExitCode.LOCK_HELD
    assert "offers no control" in outcome.message
    assert len(nobody.sent) == 1, (
        "the first command found nobody, so no other was tried"
    )
    assert setup.names() == {} and setup.plans.writes == 0
