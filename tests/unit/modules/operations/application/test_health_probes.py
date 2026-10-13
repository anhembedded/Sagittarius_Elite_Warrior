"""The host runs the declared probes before each snapshot, without ever stopping it (`EPIC-038D`)."""

from __future__ import annotations

import logging
import threading

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_health_probe import IHealthProbe
from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    HealthProbeDescriptor,
    IHealthProbeTable,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_probes import (
    HealthProbes,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.preflight_doubles import (
    NoPorts,
)

_LOGGER = "App.Operations.Health"


class _Table(IHealthProbeTable):
    def __init__(self, *probes: IHealthProbe) -> None:
        self._descriptors = tuple(
            HealthProbeDescriptor(p.name, lambda _r, probe=p: probe, "test")
            for p in probes
        )

    def probe_descriptors(self) -> tuple[HealthProbeDescriptor, ...]:
        return self._descriptors


class _Probe(IHealthProbe):
    def __init__(self, name: str = "scripted") -> None:
        self._name = name
        self.measured = 0
        self.fails = False

    @property
    def name(self) -> str:
        return self._name

    def measure(self) -> None:
        self.measured += 1
        if self.fails:
            raise ConnectionError("no route to host")


class _BlockedProbe(IHealthProbe):
    """Measures only once the test lets it, as an exchange that answers slowly does."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.runs = 0

    @property
    def name(self) -> str:
        return "blocked"

    def measure(self) -> None:
        self.runs += 1
        self.started.set()
        assert self.release.wait(30), "the test never released the probe"


def _probes(*probe: IHealthProbe, wait_s: float = 5.0) -> HealthProbes:
    return HealthProbes(_Table(*probe), NoPorts(), wait_s=wait_s)


def test_every_declared_probe_is_measured_on_each_run() -> None:
    first, second = _Probe("alpha"), _Probe("beta")
    probes = _probes(first, second)

    probes.run()
    probes.run()

    assert (first.measured, second.measured) == (2, 2)


def test_no_declared_probe_is_nothing_to_do() -> None:
    _probes().run()


def test_a_probe_that_raises_is_logged_once_and_the_run_goes_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    broken, fine = _Probe("alpha"), _Probe("beta")
    broken.fails = True
    probes = _probes(broken, fine)

    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        probes.run()
        probes.run()

    assert fine.measured == 2  # the other probe was not skipped
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1, "a probe failing every minute must not warn every minute"
    assert "alpha" in warnings[0].getMessage()


def test_a_probe_that_recovers_says_so_and_warns_again_if_it_fails_again(
    caplog: pytest.LogCaptureFixture,
) -> None:
    probe = _Probe("alpha")
    probes = _probes(probe)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        probe.fails = True
        probes.run()
        probe.fails = False
        probes.run()
        probe.fails = True
        probes.run()

    levels = [r.levelno for r in caplog.records if "alpha" in r.getMessage()]
    assert levels == [logging.WARNING, logging.INFO, logging.WARNING]


def test_a_slow_probe_does_not_hold_the_snapshot_back() -> None:
    probe = _BlockedProbe()
    probes = _probes(probe, wait_s=0.05)

    probes.run()  # returns after the wait although the probe has not finished

    assert probe.started.wait(5)
    probe.release.set()


def test_a_probe_still_running_is_not_started_a_second_time() -> None:
    probe = _BlockedProbe()
    probes = _probes(probe, wait_s=0.05)

    probes.run()
    assert probe.started.wait(5)
    probes.run()
    probes.run()
    probe.release.set()

    assert probe.runs == 1
