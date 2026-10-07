"""`EPIC-034E` (D5) — a key is stored only after the reader accepted it, and a
key that can withdraw is never stored."""

from __future__ import annotations

from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_key_enrolment import (
    enrol_key,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_readonly_credentials import (
    MainnetReadOnlyCredentials,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_mainnet_read_client import (
    IMainnetReadClient,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.mainnet.test_mainnet_readonly_account_reader import (
    _Client,
    _Clients,
)

_KEY = ExchangeCredentials("candidate-key", "candidate-secret")


def _enrol(client: IMainnetReadClient, store) -> VenueAccountSnapshot | ConnectFailure:
    return enrol_key(_KEY, _Clients(client), MainnetReadOnlyCredentials(store))


def test_a_read_only_key_is_checked_then_stored() -> None:
    store = InMemorySecretStore()

    answer = _enrol(_Client(), store)

    assert isinstance(answer, VenueAccountSnapshot)
    assert MainnetReadOnlyCredentials(store).resolve().credentials == _KEY


def test_a_key_that_can_trade_is_stored_too_with_its_permissions_in_the_answer() -> (
    None
):
    store = InMemorySecretStore()
    permissions: dict[str, Any] = {
        "enableReading": True,
        "enableSpotAndMarginTrading": True,
        "enableWithdrawals": False,
    }

    answer = _enrol(_Client(get_account_api_permissions=permissions), store)

    assert isinstance(answer, VenueAccountSnapshot)
    assert answer.key_permissions is not None and answer.key_permissions.can_trade_spot
    assert store.secrets


def test_a_key_that_can_withdraw_is_never_stored() -> None:
    store = InMemorySecretStore()
    permissions: dict[str, Any] = {
        "enableReading": True,
        "enableSpotAndMarginTrading": False,
        "enableWithdrawals": True,
    }

    answer = _enrol(_Client(get_account_api_permissions=permissions), store)

    assert isinstance(answer, ConnectFailure)
    assert answer.kind is ConnectionFailureKind.WITHDRAWAL_ENABLED
    assert store.secrets == {}


def test_a_key_the_exchange_could_not_be_asked_about_is_never_stored() -> None:
    store = InMemorySecretStore()
    client = _Client(get_account_api_permissions=RuntimeError("never"))

    with pytest.raises(RuntimeError):
        _enrol(client, store)

    assert store.secrets == {}


def test_a_good_key_on_a_machine_with_no_keyring_says_it_could_not_be_kept() -> None:
    with pytest.raises(SecretStoreUnavailableError):
        _enrol(_Client(), UnavailableSecretStore())
