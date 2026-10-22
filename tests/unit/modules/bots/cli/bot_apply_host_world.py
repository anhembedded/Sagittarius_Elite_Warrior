"""`EPIC-045C` - the shared world of the `bot apply` beside a host tests: a plan file, the verb's arguments, one store and record.

The host here is `InProcessHost`: the operator's requests reach the host's real handlers over an in-memory store and
applied-plan record, so what these tests assert is what a host would do, and the record they compare is the one an offline
apply writes for the same plan (decision C6).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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
    verb_world,
)

S = BotLifecycleState
PRINTER = ReportPrinter(ReportFormats.default())
SECOND_COPY = InstanceAccess.declined("Another copy holds the data root.")
OLD = {"lower": "60000", "upper": "70000"}


def an_entry(name: str, desired: str = "running", **params: str) -> dict[str, object]:
    return {
        "name": name,
        "kind": "grid",
        "venue": "spot_testnet",
        "symbol": "BTCUSDT",
        "params": params or OLD,
        "desired_state": desired,
    }


def a_plan_file(tmp_path: Path, *entries: dict[str, object]) -> Path:
    path = tmp_path / "plan.json"
    path.write_text(
        json.dumps({"schema": "sew.bot-plan/1", "bots": list(entries)}),
        encoding="utf-8",
    )
    return path


def verb_args(path: Path, **values: object) -> argparse.Namespace:
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


class Setup:
    """One store and record; applied once beside a host and (in a twin) offline, to compare."""

    def __init__(self) -> None:
        self.world = CommandWorld()
        self.plans = MemoryAppliedPlanStore()
        self.host = InProcessHost(self.world, self.plans)

    def beside_a_host(self, path: Path, **values: object):
        return ApplyBotPlanVerb().run(
            verb_args(path, **values),
            verb_world(
                self.world,
                PRINTER,
                plans=self.plans,
                instance=SECOND_COPY,
                host_control=self.host,
            ),
        )

    def offline(self, path: Path, **values: object):
        return ApplyBotPlanVerb().run(
            verb_args(path, **values),
            verb_world(self.world, PRINTER, plans=self.plans),
        )

    def seed(self) -> None:
        save_bot(self.world.store, "aaaaaa", S.STOPPED, "edited", OLD)
        save_bot(self.world.store, "bbbbbb", S.STOPPED, "same", OLD)
        save_bot(self.world.store, "cccccc", S.STOPPED, "retired", OLD)
        save_bot(self.world.store, "dddddd", S.RUNNING, "busy", OLD)
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


def wishes_of(setup: Setup) -> set[tuple[str, str, DesiredState]]:
    assert setup.plans.plan is not None
    return {(row.name, row.venue, row.desired_state) for row in setup.plans.plan.bots}
