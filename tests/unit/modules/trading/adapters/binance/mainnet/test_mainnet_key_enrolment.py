"""`EPIC-034` D5, D10 — a key is stored only after the gate accepted it, and a key
that can withdraw is never stored."""

from __future__ import annotations

from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_key_enrolment import (
    enrol_key,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    MainnetCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)

_KEY = ExchangeCredentials("candidate-key", "candidate-secret")
_SPOT = TradingVenue.SPOT_MAINNET


class _Client:
    def __init__(self, answer: dict[str, Any] | Exception) -> None:
        self._answer = answer

    def get_account_api_permissions(self) -> dict[str, Any]:
        if isinstance(self._answer, Exception):
            raise self._answer
        return self._answer


def _clients(answer: dict[str, Any] | Exception):
    return lambda _venue, _credentials: _Client(answer)


def _flags(*, withdraw: bool = False, trade: bool = False) -> dict[str, Any]:
    return {
        "enableReading": True,
        "enableSpotAndMarginTrading": trade,
        "enableWithdrawals": withdraw,
    }


@pytest.mark.parametrize(
    "venue", [TradingVenue.SPOT_MAINNET, TradingVenue.FUTURES_MAINNET]
)
def test_an_acceptable_key_is_checked_then_stored_under_its_own_venue(
    venue: TradingVenue,
) -> None:
    store = InMemorySecretStore()

    refused = enrol_key(
        venue, _KEY, MainnetCredentialsProvider(store, venue), _clients(_flags())
    )

    assert refused is None
    assert MainnetCredentialsProvider(store, venue).resolve().credentials == _KEY


def test_a_key_that_can_trade_is_stored_too() -> None:
    store = InMemorySecretStore()

    assert (
        enrol_key(
            _SPOT,
            _KEY,
            MainnetCredentialsProvider(store, _SPOT),
            _clients(_flags(trade=True)),
        )
        is None
    )
    assert store.secrets


def test_a_key_that_can_withdraw_is_never_stored() -> None:
    store = InMemorySecretStore()

    refused = enrol_key(
        _SPOT,
        _KEY,
        MainnetCredentialsProvider(store, _SPOT),
        _clients(_flags(withdraw=True)),
    )

    assert refused is not None
    assert refused.kind is ConnectionFailureKind.WITHDRAWAL_ENABLED
    assert store.secrets == {}


def test_a_key_the_exchange_could_not_be_asked_about_is_never_stored() -> None:
    store = InMemorySecretStore()
    refused = enrol_key(
        _SPOT,
        _KEY,
        MainnetCredentialsProvider(store, _SPOT),
        _clients(ValueError("garbled")),
    )

    assert refused is not None
    assert store.secrets == {}


def test_a_good_key_on_a_machine_with_no_keyring_says_it_could_not_be_kept() -> None:
    with pytest.raises(SecretStoreUnavailableError):
        enrol_key(
            _SPOT,
            _KEY,
            MainnetCredentialsProvider(UnavailableSecretStore(), _SPOT),
            _clients(_flags()),
        )


@pytest.mark.parametrize(
    "venue", [TradingVenue.SPOT_TESTNET, TradingVenue.FUTURES_TESTNET]
)
def test_a_testnet_key_is_never_put_in_the_keyring(venue: TradingVenue) -> None:
    store = InMemorySecretStore()

    with pytest.raises(ValueError, match="not a mainnet venue"):
        enrol_key(
            venue, _KEY, MainnetCredentialsProvider(store, venue), _clients(_flags())
        )

    assert store.secrets == {}
