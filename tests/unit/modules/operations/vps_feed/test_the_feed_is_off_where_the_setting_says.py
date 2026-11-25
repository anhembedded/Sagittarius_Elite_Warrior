"""`EPIC-047H` - a process whose setting turns the feed off (the GUI's) starts no worker and writes no file."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.composition.vps_feed_host import (
    VpsFeedHost,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.vps_feed_settings import (
    VpsFeedSettings,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.bot_log.bot_log_world import (
    NumberClock,
)


class _Container:
    """Resolves only the settings: anything the feed would build after them fails the test."""

    def __init__(self, settings: VpsFeedSettings) -> None:
        self._settings = settings

    def resolve(self, key: object) -> object:
        if key is VpsFeedSettings:
            return self._settings
        raise AssertionError(f"the feed built {key} although it is off")


class _Context:
    def __init__(self, container: _Container) -> None:
        self.container = container


def test_a_feed_turned_off_resolves_nothing_after_its_settings() -> None:
    off = replace(VpsFeedSettings.judged(120, 3.0, True), feed_enabled=False)

    VpsFeedHost().begin(_Context(_Container(off)), clock=None)  # type: ignore[arg-type]


def _bot_log_handlers() -> list[object]:
    return [
        h
        for h in logging.getLogger("App.Bots").handlers
        if type(h).__name__ == "BotLogHandler"
    ]


def test_a_feed_turned_off_attaches_no_bot_log_handler() -> None:
    off = replace(VpsFeedSettings.judged(120, 3.0, True), feed_enabled=False)

    VpsFeedHost().begin(_Context(_Container(off)), clock=None)  # type: ignore[arg-type]

    assert _bot_log_handlers() == []


def test_a_bot_log_turned_off_attaches_no_handler_while_the_rest_of_the_feed_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEW_DATA_ROOT", str(tmp_path))
    quiet = replace(VpsFeedSettings.judged(0, 3.0, False), log_enabled=False)

    class _Resolving(_Container):
        def resolve(self, key: object) -> object:
            return object() if key is not VpsFeedSettings else self._settings

    VpsFeedHost().begin(_Context(_Resolving(quiet)), clock=None)  # type: ignore[arg-type]

    assert _bot_log_handlers() == []
    assert not (tmp_path / "state" / "bot-logs").exists()


def test_a_bot_log_turned_on_attaches_one_handler_and_end_removes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEW_DATA_ROOT", str(tmp_path))
    on = VpsFeedSettings.judged(0, 3.0, False)

    class _Resolving(_Container):
        def resolve(self, key: object) -> object:
            return object() if key is not VpsFeedSettings else self._settings

    clock = NumberClock()
    host = VpsFeedHost()
    host.begin(_Context(_Resolving(on)), clock=clock)  # type: ignore[arg-type]
    try:
        assert len(_bot_log_handlers()) == 1
    finally:
        host.end()

    assert _bot_log_handlers() == []
