"""`EPIC-039E` — the settings gate of a bot's venue is chosen by the venue's profile.

@details Business promise: a Spot venue has nothing to ensure and is never asked anything; a
Futures venue goes through the Futures gate; a venue that trades no market is a named
refusal, never a pass.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue_profiles_by_market import (
    VenueProfilesByMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue_settings_gate_futures import (
    FuturesSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue_settings_gate_spot import (
    SpotSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue_settings_gates import (
    VenueSettingsGates,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.margin_mode import MarginMode
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    GateOutcome,
    GateRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.futures_world import (
    FUTURES,
    SYMBOL,
    FuturesWorld,
)


def _gates(world: FuturesWorld) -> VenueSettingsGates:
    return VenueSettingsGates(
        VenueProfilesByMarket(),
        {
            ExposureKind.INVENTORY: SpotSettingsGate(),
            ExposureKind.POSITION: FuturesSettingsGate(world.ports),
        },
    )


def test_a_spot_venue_is_ensured_without_any_request() -> None:
    world = FuturesWorld()
    request = GateRequest(TradingVenue.SPOT_TESTNET, SYMBOL, 1, MarginMode.ISOLATED)

    assert _gates(world).ensure(request).ensured
    assert _gates(world).verify(request).ensured
    assert world.settings.calls == []
    assert world.account.connection_checks == 0


def test_a_futures_venue_goes_through_the_futures_gate() -> None:
    world = FuturesWorld(leverage=5, margin_type=MarginType.CROSSED)

    result = _gates(world).ensure(GateRequest(FUTURES, SYMBOL, 3, MarginMode.ISOLATED))

    assert result.ensured
    assert world.settings.calls == ["change_margin_type", "change_leverage"]


def test_a_venue_that_trades_no_market_is_a_refusal_never_a_pass() -> None:
    request = GateRequest(TradingVenue.DISABLED, SYMBOL, 1, MarginMode.ISOLATED)

    result = _gates(FuturesWorld()).ensure(request)

    assert result.outcome is GateOutcome.SETTINGS_UNREADABLE
