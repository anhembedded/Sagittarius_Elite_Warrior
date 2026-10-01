"""PR #303 review, finding 2 — the app's fallback limits have one
definition: with nothing configured the composition root's
`TradingLimitPolicy` judges by `DEFAULT_TRADING_LIMITS`, and
`FakeOrderEntryTerms`' default limit is the same figure, so the fake cannot
keep sizing against an old default after the real one changes."""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_entry_terms import (
    FakeOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    DEFAULT_TRADING_LIMITS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager


def test_with_nothing_configured_the_gate_judges_by_the_default_limits() -> None:
    container = StdLibContainer()
    container.singleton(IConfig, DictConfig({}))
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    bind_adapters(container)

    assert container.resolve(TradingLimitPolicy).limits == DEFAULT_TRADING_LIMITS


def test_the_fakes_default_notional_limit_is_the_apps() -> None:
    assert (
        FakeOrderEntryTerms().order_notional_limit()
        == DEFAULT_TRADING_LIMITS.max_notional_per_order
    )
