"""Shared set-up for the `run` command's composed-app tests (`EPIC-038D`, `EPIC-038I`).

The composed app is the real graph `create_app()` builds; only the signal is by hand.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_plan import IBotPlan
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_shutdown_signal_source import (
    IShutdownSignalSource,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from sagittarius_engine import App

from ..bots.grid_fake_exchange import app_config


class Source(IShutdownSignalSource):
    """A signal source the test fires by hand."""

    def __init__(self) -> None:
        self.installed = False
        self.restored = 0
        self._on_signal: Callable[[], None] | None = None

    def install(self, on_signal: Callable[[], None]) -> None:
        self.installed = True
        self._on_signal = on_signal

    def restore(self) -> None:
        self.restored += 1

    def fire(self) -> None:
        assert self._on_signal is not None
        self._on_signal()


class Plan(IBotPlan):
    def __init__(self, *bot_ids: str) -> None:
        self._ids = frozenset(bot_ids)

    def exists(self) -> bool:
        return True

    def problem(self) -> str | None:
        return None

    def wants_running(self) -> frozenset[str]:
        return self._ids


class Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(f"{record.name} - {record.levelname} - {record.getMessage()}")


@contextmanager
def heard() -> Iterator[list[str]]:
    """What `App.Operations` said; the composed app turns propagation off, so `caplog` sees none."""
    handler = Lines()
    logger = logging.getLogger("App.Operations")
    logger.addHandler(handler)
    try:
        yield handler.lines
    finally:
        logger.removeHandler(handler)


def app_on(data_root: Path) -> App:
    return create_app(app_config(data_root))
