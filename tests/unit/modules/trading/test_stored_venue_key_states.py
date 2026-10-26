"""`EPIC-047C` - whether a venue has a key saved, asked of the stored key alone."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.shared_venue_inputs import (
    SharedVenueInputs,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.stored_venue_key_states import (
    StoredVenueKeyStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_key_states import (
    FakeVenueKeyStates,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.secrets.ordered_secret_stores import (
    OrderedSecretStores,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore

MAINNET = TradingVenue.FUTURES_MAINNET
SPOT_MAINNET = TradingVenue.SPOT_MAINNET


def _states(store: InMemorySecretStore) -> StoredVenueKeyStates:
    shared = SharedVenueInputs(
        container=Mock(),
        secrets_file_path="unused",
        session_states=VenueSessionStates(),
        secret_store=OrderedSecretStores.single(store),
        instance=InstanceAccess.unguarded(),
    )
    return StoredVenueKeyStates((MAINNET, SPOT_MAINNET), shared)


@pytest.fixture(autouse=True)
def _no_key_in_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "BINANCE_FUTURES_MAINNET_API_KEY",
        "BINANCE_FUTURES_MAINNET_API_SECRET",
        "BINANCE_SPOT_MAINNET_API_KEY",
        "BINANCE_SPOT_MAINNET_API_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)


def test_a_venue_with_a_stored_key_says_so() -> None:
    store = InMemorySecretStore(
        **{
            f"{MAINNET.value}_api_key": "k" * 20,
            f"{MAINNET.value}_api_secret": "s" * 20,
        }
    )

    assert _states(store).key_saved(MAINNET)


def test_a_venue_without_one_says_it_has_none_and_the_other_venues_key_does_not_count() -> (
    None
):
    store = InMemorySecretStore(
        **{
            f"{MAINNET.value}_api_key": "k" * 20,
            f"{MAINNET.value}_api_secret": "s" * 20,
        }
    )

    assert not _states(store).key_saved(SPOT_MAINNET)


def test_a_key_saved_after_the_first_question_is_seen_at_once() -> None:
    """The provider keeps its first read for the life of the process, so one kept here would go on
    saying "no key" after the enrolment script saved one."""
    store = InMemorySecretStore()
    states = _states(store)
    assert not states.key_saved(MAINNET)

    store.write(f"{MAINNET.value}_api_key", "k" * 20)
    store.write(f"{MAINNET.value}_api_secret", "s" * 20)

    assert states.key_saved(MAINNET)


def test_a_venue_that_is_not_enabled_is_refused() -> None:
    with pytest.raises(VenueNotEnabledError):
        _states(InMemorySecretStore()).key_saved(TradingVenue.SPOT_TESTNET)


def test_the_fake_follows_the_same_rules() -> None:
    fake = FakeVenueKeyStates((MAINNET, SPOT_MAINNET), (MAINNET,))

    assert fake.key_saved(MAINNET)
    assert not fake.key_saved(SPOT_MAINNET)
    with pytest.raises(VenueNotEnabledError):
        fake.key_saved(TradingVenue.SPOT_TESTNET)
