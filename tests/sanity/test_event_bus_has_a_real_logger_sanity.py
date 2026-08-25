"""Sanity: the app's event bus reports handler failures through the app's own
logger (`EPIC-008G` §4).

Not a "lost logs" fix — `EPIC-008C` already made a logger-less bus fall back to
the standard `logging` module, so failures were visible either way. What this
pins is *where* they land: the app's `ILogger`, with the app's formatter and
the app's log file, which is the file `ci-local.ps1`'s "Run Log Scan" step
reads. A failure that only reached stdlib logging could pass that scan while
still being a real defect.
"""

from __future__ import annotations

import os

import pytest
from Sagittarius_Elite_Warrior.src.main import create_app
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.utils.null_logger import NullLogger


@pytest.fixture
def booted_app():
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
    )
    app = create_app(config_manager)
    yield app
    app.stop()


def test_create_app_gives_the_bus_a_real_logger(booted_app):
    """The bus must not be holding the `FallbackLogger` that a `None` would
    have produced."""
    bus = booted_app.event_bus

    assert bus.logger is not None
    assert not isinstance(bus.logger, NullLogger)
    assert type(bus.logger).__name__ != "FallbackLogger", (
        "bus fell back to stdlib logging — main.py should pass an ILogger"
    )


def test_a_failing_handler_is_reported_to_that_logger():
    """The behaviour the wiring exists for, asserted directly rather than
    inferred from the wiring."""

    class _Recording:
        def __init__(self) -> None:
            self.errors: list[str] = []

        def error(self, message: str, extra: dict | None = None) -> None:
            self.errors.append(message)

        def __getattr__(self, _name):  # info/debug/warning/critical — unused here
            return lambda *args, **kwargs: None

    logger = _Recording()
    bus = MemoryEventBus(logger)

    def explodes(_payload):
        raise ValueError("boom")

    bus.on("sanity.event", explodes)
    bus.emit("sanity.event", {})

    assert len(logger.errors) == 1
    assert "ValueError" in logger.errors[0]
