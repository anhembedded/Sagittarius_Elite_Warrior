"""Developer mode is decided once per run, and the command line wins (SDD-05).

The behaviour change Phase 0 declares lives here: both entry points call
`resolve_dev_mode()`, so `--dev` works for the headless path too. Before this,
`python -m ...main --dev sync` set the flag on nothing at all.
"""

from __future__ import annotations

from typing import Any

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.shell.dev_mode import resolve_dev_mode


class _Config:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self._values = values or {}

    def get(self, key: str, default: Any = None, cast: type | None = None) -> Any:
        return self._values.get(key, default)

    def get_all(self) -> dict[str, Any]:
        return dict(self._values)

    def set(self, key: str, value: Any) -> None:
        self._values[key] = value


def test_off_by_default(tmp_path) -> None:
    dev_mode = resolve_dev_mode(_Config(), ["app.py"], str(tmp_path))
    assert not dev_mode.is_enabled
    assert not dev_mode.came_from_the_command_line
    assert dev_mode.config_overrides() == {}


def test_the_config_file_can_turn_it_on(tmp_path) -> None:
    dev_mode = resolve_dev_mode(
        _Config({ConfigKeys.DEV_MODE.value: True}), ["app.py"], str(tmp_path)
    )
    assert dev_mode.is_enabled
    assert not dev_mode.came_from_the_command_line
    assert dev_mode.config_overrides() == {}, "the file's value already stands"


def test_the_dev_flag_wins_over_the_file(tmp_path) -> None:
    dev_mode = resolve_dev_mode(
        _Config({ConfigKeys.DEV_MODE.value: False}), ["app.py", "--dev"], str(tmp_path)
    )
    assert dev_mode.is_enabled
    assert dev_mode.came_from_the_command_line

    overrides = dev_mode.config_overrides()
    assert overrides[ConfigKeys.DEV_MODE.value] is True
    assert overrides["log.level"] == "DEBUG"
    assert str(tmp_path) in overrides["log.file"]


def test_the_debug_flag_implies_developer_mode_and_raises_the_log_level(
    tmp_path,
) -> None:
    dev_mode = resolve_dev_mode(_Config(), ["app.py", "--debug"], str(tmp_path))
    assert dev_mode.is_enabled
    assert dev_mode.config_overrides()["log.level"] == "TRACE"


def test_a_flag_anywhere_on_the_command_line_counts(tmp_path) -> None:
    """`main.py` passes the whole `sys.argv`, including the sub-command, so the
    flag is not positional: `... sync --dev BTCUSDT` must work."""
    dev_mode = resolve_dev_mode(
        _Config(), ["main.py", "sync", "--dev", "BTCUSDT"], str(tmp_path)
    )
    assert dev_mode.is_enabled
