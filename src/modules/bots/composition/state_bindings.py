"""bots' own state: the store, the clock and the id generator (`EPIC-029B`).

Singletons, because the store holds the per-bot write locks: two instances
would each lock their own copy of a bot and serialise nothing.

@par Where the files go
`<repo root>/state/bots/`, beside `ui_state.json` in the gitignored `state/`
(`repo_state_store_locator.py`). The root is found by its landmark,
`pyproject.toml`, not by counting parent directories
(`test_no_root_is_found_by_counting.py`).
"""

from __future__ import annotations

from pathlib import Path

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
from sagittarius_engine.interfaces.i_container import IContainer

_LANDMARK = "pyproject.toml"


def repo_root() -> Path:
    """The directory holding `pyproject.toml`, searching up from this file."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / _LANDMARK).is_file():
            return candidate
    raise FileNotFoundError(f"No {_LANDMARK} above {__file__}")


def bots_directory() -> Path:
    return repo_root() / "state" / "bots"


def bind_state(container: IContainer) -> None:
    store = JsonBotStore(bots_directory())
    clock = SystemBotClock()
    container.singleton(IBotStore, store)
    container.singleton(IBotClock, clock)
    container.singleton(BotIdGenerator, BotIdGenerator())
    container.singleton(BotRestoreService, BotRestoreService(store, clock))
