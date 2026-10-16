"""What the module says about itself (`test_module_declarations.py` checks the rest)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthContributorDescriptor,
    HealthProbeDescriptor,
    IOperationsRegistry,
    PreflightCheckDescriptor,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.module import AlertingModule


class _Recorder(IOperationsRegistry):
    def __init__(self) -> None:
        self.health: list[HealthContributorDescriptor] = []

    def declare_preflight(self, descriptor: PreflightCheckDescriptor) -> None:
        raise AssertionError("alerting declares no pre-flight check")

    def declare_health(self, descriptor: HealthContributorDescriptor) -> None:
        self.health.append(descriptor)

    def declare_probe(self, descriptor: HealthProbeDescriptor) -> None:
        raise AssertionError("alerting declares no health probe")


def test_the_module_listens_to_the_bots_only() -> None:
    """`EPIC-036G`: the bot source reads `bots/contracts`; `EPIC-036B` adds `trading`."""
    module = AlertingModule()

    assert module.module_id == "alerting"
    assert module.dependencies == ["bots"]


def test_it_declares_one_health_section_named_alerting() -> None:
    recorder = _Recorder()

    AlertingModule().declare_operations(recorder)

    assert [(d.name, d.contributor_id) for d in recorder.health] == [
        ("alerting", "alerting")
    ]
