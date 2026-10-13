"""`EPIC-038F` — the shell collects what modules declare for running unattended.

Same contract as `test_cli_registry.py`: the module declares, the shell
collects, a clash fails at boot naming both modules, and the order is stable.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ContributionError
from Sagittarius_Elite_Warrior.src.core.contracts.i_health_probe import IHealthProbe
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthContributorDescriptor,
    HealthProbeDescriptor,
    PreflightCheckDescriptor,
)
from Sagittarius_Elite_Warrior.src.shell.operations_registry import (
    OperationsRegistry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.preflight_doubles import (
    ScriptedCheck,
    declared,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.status_world import (
    FixedContributor,
)


def test_declared_checks_come_back_sorted_by_id() -> None:
    registry = OperationsRegistry()
    for check_id in ("zeta", "alpha", "mid"):
        registry.declare_preflight(declared(ScriptedCheck(check_id)))

    assert [d.check_id for d in registry.descriptors()] == ["alpha", "mid", "zeta"]


def test_two_modules_claiming_one_check_id_fail_naming_both() -> None:
    registry = OperationsRegistry()
    registry.declare_preflight(declared(ScriptedCheck("clock-skew"), "trading"))

    with pytest.raises(ContributionError) as raised:
        registry.declare_preflight(
            PreflightCheckDescriptor(
                "clock-skew", lambda _r: ScriptedCheck("clock-skew"), "other"
            )
        )

    assert "'trading'" in str(raised.value)
    assert "'other'" in str(raised.value)


def test_a_module_that_declares_nothing_leaves_the_table_empty() -> None:
    assert OperationsRegistry().descriptors() == ()


# -- health contributors (`EPIC-038C`) -----------------------------------------


def _health(name: str, owner: str = "bots") -> HealthContributorDescriptor:
    return HealthContributorDescriptor(
        name, lambda _r: FixedContributor(name, {}), owner
    )


def test_declared_health_sections_come_back_sorted_by_name() -> None:
    registry = OperationsRegistry()
    for name in ("trading", "bots", "market_data"):
        registry.declare_health(_health(name))

    assert [d.name for d in registry.health_descriptors()] == [
        "bots",
        "market_data",
        "trading",
    ]


def test_two_modules_claiming_one_section_fail_naming_both() -> None:
    registry = OperationsRegistry()
    registry.declare_health(_health("bots", "bots"))

    with pytest.raises(ContributionError) as raised:
        registry.declare_health(_health("bots", "intruder"))

    assert "'bots'" in str(raised.value)
    assert "'intruder'" in str(raised.value)


def test_checks_and_health_sections_are_separate_tables() -> None:
    registry = OperationsRegistry()
    registry.declare_preflight(declared(ScriptedCheck("same-word")))
    registry.declare_health(_health("same-word"))

    assert [d.check_id for d in registry.descriptors()] == ["same-word"]
    assert [d.name for d in registry.health_descriptors()] == ["same-word"]


# -- health probes (`EPIC-038D`) -------------------------------------------------


class _Probe(IHealthProbe):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def measure(self) -> None:
        return None


def _probe(name: str, owner: str = "trading") -> HealthProbeDescriptor:
    return HealthProbeDescriptor(name, lambda _r: _Probe(name), owner)


def test_declared_probes_come_back_sorted_by_name() -> None:
    registry = OperationsRegistry()
    for name in ("zeta", "alpha", "mid"):
        registry.declare_probe(_probe(name))

    assert [d.name for d in registry.probe_descriptors()] == ["alpha", "mid", "zeta"]


def test_two_modules_claiming_one_probe_fail_naming_both() -> None:
    registry = OperationsRegistry()
    registry.declare_probe(_probe("clock-skew", "trading"))

    with pytest.raises(ContributionError) as raised:
        registry.declare_probe(_probe("clock-skew", "other"))

    assert "'trading'" in str(raised.value)
    assert "'other'" in str(raised.value)


def test_probes_are_a_table_apart_from_checks_and_sections() -> None:
    registry = OperationsRegistry()
    registry.declare_probe(_probe("clock-skew"))

    assert registry.descriptors() == ()
    assert registry.health_descriptors() == ()
