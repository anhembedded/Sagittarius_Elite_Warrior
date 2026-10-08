"""bots' own state: the store, the clocks and the id generator (`EPIC-029B`).

Singletons, because the store holds the per-bot write locks: two instances
would each lock their own copy of a bot and serialise nothing.

@par Where the files go
`bots.state_dir` (`ConfigKeys.BOTS_STATE_DIR`) when set, else
`<data root>/state/bots/`, beside `ui_state.json` in the gitignored `state/`
(`repo_state_store_locator.py`). The data root is the repository root unless
`SEW_DATA_ROOT` moves it (`core/repo_root.py`, `EPIC-030M`). The key exists so a test boot of the
real composition root (the sanity tier) can point the store elsewhere: the
restore at `boot()` rewrites RUNNING and PAUSED bots, and must never touch a
live bot's file (PR #318 review).
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import data_root
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.system_bot_clock import (
    SystemBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.system_monotonic_clock import (
    SystemMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_restore_service import (
    BotRestoreService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.notifying_bot_store import (
    NotifyingBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.read_only_bot_store import (
    ReadOnlyBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotIdGenerator
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer


def bots_directory(config: IConfig) -> Path:
    configured = config.get(ConfigKeys.BOTS_STATE_DIR.value)
    if configured:
        return Path(str(configured))
    return data_root() / "state" / "bots"


def bind_state(container: IContainer) -> None:
    """Lazy factories: `register()` may only bind, never resolve
    (`registering_container.py`), and the store needs `IConfig`."""
    container.singleton(IBotStore, _build_store)
    container.singleton(IBotClock, SystemBotClock())
    container.singleton(IMonotonicClock, SystemMonotonicClock())
    container.singleton(BotIdGenerator, BotIdGenerator())
    container.singleton(BotRestoreService, _build_restore_service)


def _build_store(container: IContainer) -> IBotStore:
    """The JSON store, announcing every write (`EPIC-029F`, `BotChangedEvent`);
    read-only when another copy of the app holds the data root (`EPIC-035H`)."""
    store = NotifyingBotStore(
        JsonBotStore(bots_directory(container.resolve(IConfig))),
        container.resolve(IEventPublisher),
    )
    instance = container.resolve(IInstanceAccess)
    return ReadOnlyBotStore(store, instance.reason) if instance.read_only else store


def _build_restore_service(container: IContainer) -> BotRestoreService:
    return BotRestoreService(container.resolve(IBotStore), container.resolve(IBotClock))
