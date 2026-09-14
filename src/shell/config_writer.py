"""`IConfigWriter` over the Engine's `ConfigManager` (SDD).

The Settings sections and the developer-mode switch need to write two or three
keys and then save. Today `settings_presenter.py` gets there by downcasting
(`isinstance(self.config, ConfigManager)`) because `IConfig` has `set()` but not
`save()`. This adapter is the port they should have had: the shell owns the one
`ConfigManager` and hands out the ability to write, without handing out the
class.

`save()` raises `OSError` for a failed write and `ValueError` when no writable
file was loaded — both are real, both are the caller's to report, so neither is
swallowed here.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager


class ConfigManagerWriter(IConfigWriter):
    def __init__(self, config_manager: ConfigManager) -> None:
        self._config_manager = config_manager

    def set(self, key: str, value: object) -> None:
        self._config_manager.set(key, value)

    def save(self) -> None:
        self._config_manager.save()
