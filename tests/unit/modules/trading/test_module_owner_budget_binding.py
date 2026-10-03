"""`EPIC-029` ADR D6/O1 — the owner-budget pieces against the real wiring.

@details The Engine's real `StdLibContainer` and `DictConfig`, and the same
`bind_adapters()`/`bind_state()`/`bind_commands()` `TradingModule.register()`
calls: the caps read the three approved configuration keys, and the
registration handler resolves with every collaborator it needs, so a missing
binding fails here rather than at a bot's first registration.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.register_owner_budget import (
    RegisterOwnerBudgetCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.command_bindings import (
    bind_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
    OwnerBudgetCaps,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager


def _container(config: dict[str, object]) -> StdLibContainer:
    container = StdLibContainer()
    container.singleton(IConfig, DictConfig(config))
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    bind_adapters(container)
    bind_state(container)
    bind_commands(container)
    return container


def test_the_caps_read_the_approved_configuration_keys() -> None:
    caps = _container(
        {
            ConfigKeys.TRADING_BOT_LIMITS_MAX_OPEN_ORDERS.value: 40,
            ConfigKeys.TRADING_BOT_LIMITS_MIN_ORDER_SPACING_MS.value: 500,
            ConfigKeys.TRADING_BOT_LIMITS_MAX_ORDERS_PER_MINUTE.value: 30,
        }
    ).resolve(OwnerBudgetCaps)

    assert caps == OwnerBudgetCaps(40, timedelta(milliseconds=500), 30)


def test_the_caps_default_to_the_approved_values() -> None:
    assert _container({}).resolve(OwnerBudgetCaps) == DEFAULT_OWNER_BUDGET_CAPS


def test_the_registration_handler_resolves() -> None:
    handler = _container({}).resolve(RegisterOwnerBudgetCommandHandler)
    assert isinstance(handler, RegisterOwnerBudgetCommandHandler)
