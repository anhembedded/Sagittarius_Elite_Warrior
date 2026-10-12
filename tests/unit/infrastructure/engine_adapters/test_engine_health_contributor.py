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
