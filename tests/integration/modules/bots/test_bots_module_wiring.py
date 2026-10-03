"""`EPIC-029B` — `BotsModule.register()` binds every handler, and `boot()` restores.

A test that builds its own handlers proves nothing about the container
(`CS-002`, `CS-003`); the handlers are transient, so a missing binding would
only surface at the first dispatch. This file resolves each one from a real
`StdLibContainer` after `register()`, and checks that `boot()` runs the D12
restore against the configured store. PR #318 review, E12/E15.

Integration rather than unit because the store needs a directory (`tmp_path`,
through `bots.state_dir`).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import (
    ICommandHandler,
    IQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot import (
    GetBotQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot import (
    DeleteBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot import (
    PauseBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_store import (
    sample_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotLifecycle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.module import BotsModule
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig

COMMANDS = (
    CreateBotCommand,
    EditBotCommand,
    StartBotCommand,
    PauseBotCommand,
    ResumeBotCommand,
    StopBotCommand,
    DeleteBotCommand,
)
QUERIES = (ListBotsQuery, GetBotQuery)


def _registered(state_dir: Path) -> tuple[BotsModule, SimpleNamespace]:
    container = StdLibContainer()
    container.singleton(IConfig, DictConfig({"bots.state_dir": str(state_dir)}))
    context = SimpleNamespace(container=container, event_bus=MemoryEventBus())
    module = BotsModule()
    module.register(context)
    return module, context


@pytest.mark.parametrize("command", COMMANDS, ids=lambda c: c.__name__)
def test_every_command_resolves_to_its_handler(tmp_path: Path, command: type) -> None:
    _, context = _registered(tmp_path)
    assert isinstance(context.container.resolve(command), ICommandHandler)


@pytest.mark.parametrize("query", QUERIES, ids=lambda q: q.__name__)
def test_every_query_resolves_to_its_handler(tmp_path: Path, query: type) -> None:
    _, context = _registered(tmp_path)
    assert isinstance(context.container.resolve(query), IQueryHandler)


def test_the_store_is_the_configured_directory(tmp_path: Path) -> None:
    _, context = _registered(tmp_path)
    store = context.container.resolve(IBotStore)
    store.save(sample_bot())
    assert (tmp_path / "abc123.json").is_file()


def test_boot_restores_a_running_bot_as_recovering(tmp_path: Path) -> None:
    original = sample_bot()
    bot = original.bot
    JsonBotStore(tmp_path).save(
        StoredBot(
            type(bot)(
                bot.bot_id,
                bot.definition,
                BotLifecycle(BotLifecycleState.RUNNING),
                bot.created_at,
            )
        )
    )
    module, context = _registered(tmp_path)

    module.boot(context)

    assert JsonBotStore(tmp_path).load(BotId("abc123")).bot.state is (
        BotLifecycleState.RECOVERING
    )
