"""
@brief `EngineConfigReader` — implements `IConfigReader` on top of the
engine's `IConfig`.

@details One of the two adapters `EPIC-008F`'s acceptance bar required but its
numbered requirements did not list (see
`application/ports/i_config_reader.py`). Infrastructure is where naming
`IConfig` is allowed (`code-rule.md` §5).
"""

from typing import Any

from Sagittarius_Elite_Warrior.src.application.ports.i_config_reader import (
    IConfigReader,
)
from sagittarius_engine.interfaces.i_config import IConfig


class EngineConfigReader(IConfigReader):
    """
    @brief Reads configuration through the engine's config service.
    """

    def __init__(self, config: IConfig) -> None:
        self._config = config

    def get(self, key: str, default: Any = None) -> Any:
        """@brief Returns the configured value for `key`, else `default`."""
        return self._config.get(key, default)
