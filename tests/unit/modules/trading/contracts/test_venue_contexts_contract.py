"""`EPIC-028B` — the real `VenueContexts` and the verified fake both pass
`VenueContextsContract`.

@details The real one is built by the same `bind_adapters()`/`bind_state()`
`TradingModule.register()` calls, over the Engine's real container, config
and event bus; the `ITaskManager` is only stored, never started.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.composition.adapter_bindings import (
    bind_adapters,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.state_bindings import (
    bind_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly import (
    VenueAssembly,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_contexts import (
    VenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_venue_contexts import (
    VenueContextsContract,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager


def _real() -> IVenueContexts:
    container = StdLibContainer()
    container.singleton(IConfig, DictConfig())
    container.singleton(IEventBus, MemoryEventBus())
    container.singleton(ITaskManager, Mock())
    bind_adapters(container)
    bind_state(container)
    return container.resolve(IVenueContexts)


class TestVenueContexts(VenueContextsContract):
    @pytest.fixture
    def impl(self) -> IVenueContexts:
        return _real()

    @pytest.fixture
    def impl_off(self) -> IVenueContexts:
        """`EPIC-034B`: the composition root always serves every venue, so
        "nothing enabled" is built by hand — the class still owes the port's
        rule for it (`VenueContexts`'s `enabled` argument is a plain tuple)."""
        return VenueContexts(
            (),
            lambda venue: cast(
                VenueAssembly, SimpleNamespace(context=fake_venue_context(venue))
            ),
        )


class TestFakeVenueContexts(VenueContextsContract):
    @pytest.fixture
    def impl(self) -> IVenueContexts:
        return FakeVenueContexts(
            fake_venue_context(TradingVenue.FUTURES_TESTNET),
            fake_venue_context(TradingVenue.SPOT_TESTNET),
        )

    @pytest.fixture
    def impl_off(self) -> IVenueContexts:
        return FakeVenueContexts(fake_venue_context(TradingVenue.DISABLED))
