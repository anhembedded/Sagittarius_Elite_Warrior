"""The trading adapters that import the exchange SDK, named by import path (`PRO-014`).

`python-binance` costs about 0.4 s to import, and a run that never reaches the exchange
(`bot list` reads a file) should not pay it. A composition file that imported
`FuturesSessionFactory` at its head made every run pay at boot; these functions import the
class at the first call, which is the first time something resolves the port it answers.
`adapter_bindings.py` is the only caller.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.modules.trading.composition.shared_venue_inputs import (
    SharedVenueInputs,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_key_environment_probe import (
    IKeyEnvironmentProbe,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionFactory,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly import (
        VenueAssembly,
    )
    from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
        TradingVenue,
    )

_ADAPTERS = "Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance"

_SESSION_FACTORY: Deferred[ITradingSessionFactory] = Deferred(
    f"{_ADAPTERS}.futures_session_factory:FuturesSessionFactory"
)
_VENUE_ASSEMBLY: Deferred[VenueAssembly] = Deferred(
    "Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly:VenueAssembly"
)
_STORED_CREDENTIALS: Deferred[IExchangeCredentialsProvider] = Deferred(
    "Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly:stored_credentials_provider"
)
_KEY_ENVIRONMENT_PROBE: Deferred[IKeyEnvironmentProbe] = Deferred(
    f"{_ADAPTERS}.key_environment_probe:BinanceKeyEnvironmentProbe"
)


def new_session_factory() -> ITradingSessionFactory:
    """A `FuturesSessionFactory`; the SDK is imported by this call."""
    return _SESSION_FACTORY()


def new_key_environment_probe() -> IKeyEnvironmentProbe:
    """A `BinanceKeyEnvironmentProbe`; the SDK is imported by this call."""
    return _KEY_ENVIRONMENT_PROBE()


def new_venue_assembly(venue: TradingVenue, shared: SharedVenueInputs) -> VenueAssembly:
    """The adapters of one venue, built over `shared`; the SDK is imported by this call."""
    return _VENUE_ASSEMBLY(venue, shared)


def new_stored_credentials_provider(
    venue: TradingVenue, shared: SharedVenueInputs
) -> IExchangeCredentialsProvider:
    """The provider of `venue`'s saved key (`EPIC-047C`); `venue_assembly` is imported by this call,
    so a run that never asks whether a key is saved does not pay for the exchange adapters."""
    return _STORED_CREDENTIALS(venue, shared)
