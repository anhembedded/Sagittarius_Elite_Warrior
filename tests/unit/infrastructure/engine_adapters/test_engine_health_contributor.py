"""The Engine's own health check, reported as the `engine` section (`EPIC-038C`)."""

from __future__ import annotations

import json

from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.engine_health_contributor import (
    EngineHealthContributor,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces import IContainer


def _contributor() -> EngineHealthContributor:
    container = StdLibContainer()
    container.singleton(IContainer, container)
    return EngineHealthContributor(container, MemoryEventBus())


def test_the_engines_result_is_reported_not_measured_again() -> None:
    section = _contributor().snapshot()

    assert section["verdict"] == "healthy"
    assert section["components"] == {
        "container": "ok",
        "event_bus": "ok",
        "database": "not configured",
    }


def test_the_section_is_json_ready_and_named_engine() -> None:
    contributor = _contributor()

    assert contributor.name == "engine"
    assert json.dumps(dict(contributor.snapshot()))


def test_a_failed_engine_check_is_a_degraded_section() -> None:
    """The Engine's `unhealthy` is mapped to the general rule, so `status` exits 11."""
    container = StdLibContainer()  # no IContainer bound: the Engine's own check fails
    section = EngineHealthContributor(container, MemoryEventBus()).snapshot()

    assert section["verdict"] == "unhealthy"
    assert section["status"] == "degraded"
    assert section["components"]["container"].startswith("error")  # type: ignore[index]
    assert "reason" in section


def test_a_healthy_engine_check_sets_no_status_key() -> None:
    assert "status" not in _contributor().snapshot()
