"""`EPIC-035H` — a venue's client factory is the read-only one exactly when the
instance is read-only, and the assembly asks the instance, not a flag."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.read_only_trading_client_factory import (
    ReadOnlyTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_assembly import (
    SharedVenueInputs,
    VenueAssembly,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore


def _assembly(instance: InstanceAccess | None) -> VenueAssembly:
    shared = SharedVenueInputs(
        container=Mock(),
        secrets_file_path="unused",
        session_states=VenueSessionStates(),
        secret_store=InMemorySecretStore(),
        instance=InstanceAccess.unguarded() if instance is None else instance,
    )
    return VenueAssembly(TradingVenue.SPOT_TESTNET, shared)


def test_a_writable_instance_gets_the_venues_own_factory() -> None:
    factory = _assembly(None).client_factory

    assert not isinstance(factory, ReadOnlyTradingClientFactory)


def test_a_read_only_instance_gets_the_read_only_factory(tmp_path: Path) -> None:
    first = InstanceAccess.acquire(tmp_path / "instance.lock")
    second = InstanceAccess.acquire(tmp_path / "instance.lock")

    factory = _assembly(second).client_factory

    assert isinstance(factory, ReadOnlyTradingClientFactory)
    first.release()
