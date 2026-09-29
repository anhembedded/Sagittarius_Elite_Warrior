"""`EPIC-028B` — the real `VenueTradingPortsRegistry` and the verified fake
both pass `VenueTradingPortsContract`."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_trading_ports_registry import (
    VenueTradingPortsRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.contract_venue_trading_ports import (
    VenueTradingPortsContract,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    venue_context,
)

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET


class TestVenueTradingPortsRegistry(VenueTradingPortsContract):
    @pytest.fixture
    def impl(self) -> IVenueTradingPorts:
        return VenueTradingPortsRegistry(
            Mock(spec=ICommandDispatcher),
            FakeVenueContexts(venue_context(_FUTURES), venue_context(_SPOT)),
            VenueSessionStates(),
        )


class TestFakeVenueTradingPorts(VenueTradingPortsContract):
    @pytest.fixture
    def impl(self) -> IVenueTradingPorts:
        return FakeVenueTradingPorts(
            fake_venue_ports(_FUTURES), fake_venue_ports(_SPOT)
        )
