"""The two configuration ports `LiveStrategyConfigStore` takes, over one
in-memory `DictConfig`.

`EPIC-030D` — the store reads through `IConfigReader` and writes through
`IConfigWriter` (the application's own ports) instead of the Engine's
`IConfig`. The reader here is the production adapter (`EngineConfigReader`);
the writer derives from the port (`testing-rule.md` §2) and records every
`save()`, since *whether the store persisted* is half of what a save means.
Both wrap the same `DictConfig`, exactly as both production adapters wrap the
same `ConfigManager`, so a value written is the value read back.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_config_reader import IConfigReader
from Sagittarius_Elite_Warrior.src.core.contracts.i_config_writer import IConfigWriter
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.config_reader_adapter import (
    EngineConfigReader,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_config_store import (
    LiveStrategyConfigStore,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.interfaces.i_container import IContainer


class DictConfigWriter(IConfigWriter):
    """`IConfigWriter` over a `DictConfig`: `set()` is real, `save()` counts."""

    def __init__(self, config: DictConfig) -> None:
        self._config = config
        self.saves = 0

    def set(self, key: str, value: object) -> None:
        self._config.set(key, value)

    def save(self) -> None:
        self.saves += 1


def in_memory_config_store(
    config: DictConfig, writer: DictConfigWriter | None = None
) -> LiveStrategyConfigStore:
    """A store reading and writing `config`; pass `writer` to count saves."""
    return LiveStrategyConfigStore(
        EngineConfigReader(config), writer or DictConfigWriter(config)
    )


def bind_config_ports(container: IContainer, config: DictConfig) -> None:
    """Binds both ports over `config`, as `shell/composition_root.py` binds
    them over the one `ConfigManager`."""
    container.singleton(IConfigReader, EngineConfigReader(config))
    container.singleton(IConfigWriter, DictConfigWriter(config))
