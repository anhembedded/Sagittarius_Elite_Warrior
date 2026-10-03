"""bots' own state: the store, the clock and the id generator (`EPIC-029B`).

Singletons, because the store holds the per-bot write locks: two instances
would each lock their own copy of a bot and serialise nothing.

@par Where the files go
`bots.state_dir` (`ConfigKeys.BOTS_STATE_DIR`) when set, else
`<repo root>/state/bots/`, beside `ui_state.json` in the gitignored `state/`
(`repo_state_store_locator.py`). The root is found by its landmark,
`pyproject.toml`, not by counting parent directories
(`test_no_root_is_found_by_counting.py`). The key exists so a test boot of the
real composition root (the sanity tier) can point the store elsewhere: the
restore at `boot()` rewrites RUNNING and PAUSED bots, and must never touch a
live bot's file (PR #318 review).
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.system_bot_clock import (
    SystemBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_restore_service import (
    BotRestoreService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotIdGenerator
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer

_LANDMARK = "pyproject.toml"


def repo_root() -> Path:
    """The directory holding `pyproject.toml`, searching up from this file."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / _LANDMARK).is_file():
            return candidate
    raise FileNotFoundError(f"No {_LANDMARK} above {__file__}")


def bots_directory(config: IConfig) -> Path:
    configured = config.get(ConfigKeys.BOTS_STATE_DIR.value)
    if configured:
        return Path(str(configured))
    return repo_root() / "state" / "bots"


def bind_state(container: IContainer) -> None:
    """Lazy factories: `register()` may only bind, never resolve
    (`registering_container.py`), and the store needs `IConfig`."""
    container.singleton(IBotStore, _build_store)
    container.singleton(IBotClock, SystemBotClock())
    container.singleton(BotIdGenerator, BotIdGenerator())
    container.singleton(BotRestoreService, _build_restore_service)


def _build_store(container: IContainer) -> IBotStore:
    return JsonBotStore(bots_directory(container.resolve(IConfig)))


def _build_restore_service(container: IContainer) -> BotRestoreService:
    return BotRestoreService(container.resolve(IBotStore), container.resolve(IBotClock))
