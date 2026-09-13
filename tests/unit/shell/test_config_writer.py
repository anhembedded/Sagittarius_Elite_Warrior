"""Writing configuration through a port, not a downcast (SDD).

`settings_presenter.py` reaches `save()` today with
`isinstance(self.config, ConfigManager)`. That works and is honest about being a
workaround; this adapter is the port it was working around.
"""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts import IConfigWriter
from Sagittarius_Elite_Warrior.src.shell.config_writer import ConfigManagerWriter
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


@pytest.fixture
def writable(tmp_path):
    path = tmp_path / "user_config.json"
    path.write_text(json.dumps({"existing": 1}), encoding="utf-8")
    manager = ConfigManager()
    manager.load_json(str(path), writable=True)
    return manager, path


def test_it_is_the_port_and_nothing_more(writable) -> None:
    manager, _path = writable
    writer = ConfigManagerWriter(manager)
    assert isinstance(writer, IConfigWriter)
    assert sorted(name for name in vars(type(writer)) if not name.startswith("_")) == [
        "save",
        "set",
    ]


def test_set_then_save_reaches_the_file(writable) -> None:
    manager, path = writable
    writer = ConfigManagerWriter(manager)

    writer.set("dev.mode", True)
    writer.save()

    assert json.loads(path.read_text(encoding="utf-8"))["dev.mode"] is True


def test_set_alone_does_not_touch_the_file(writable) -> None:
    """A settings section sets several keys and saves once; that is why these
    are two calls."""
    manager, path = writable
    ConfigManagerWriter(manager).set("dev.mode", True)
    assert "dev.mode" not in json.loads(path.read_text(encoding="utf-8"))


def test_existing_keys_survive_a_save(writable) -> None:
    manager, path = writable
    writer = ConfigManagerWriter(manager)
    writer.set("dev.mode", True)
    writer.save()
    assert json.loads(path.read_text(encoding="utf-8"))["existing"] == 1


def test_saving_without_a_writable_file_raises() -> None:
    """Silently dropping the write would make the developer-mode switch look
    like it worked."""
    manager = ConfigManager()
    writer = ConfigManagerWriter(manager)
    writer.set("dev.mode", True)
    with pytest.raises(ValueError):
        writer.save()
