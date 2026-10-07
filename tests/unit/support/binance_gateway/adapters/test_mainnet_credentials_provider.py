"""`EPIC-034` D10, D11 — a mainnet venue's key resolves from its own two variables,
then from the operating system's keyring, and from nowhere else: never a testnet
pair, never another mainnet venue's, never `secrets.local.json`."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    FUTURES_ENV_API_KEY,
    FUTURES_ENV_API_SECRET,
    FUTURES_MAINNET_ENV_API_KEY,
    FUTURES_MAINNET_ENV_API_SECRET,
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
    SPOT_MAINNET_ENV_API_KEY,
    SPOT_MAINNET_ENV_API_SECRET,
    EnvFirstCredentialsProvider,
    MainnetCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.secrets_file_source import (
    SecretsFileSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
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

_SPOT = TradingVenue.SPOT_MAINNET
_FUTURES = TradingVenue.FUTURES_MAINNET
_NAMES = {
    _SPOT: (SPOT_MAINNET_ENV_API_KEY, SPOT_MAINNET_ENV_API_SECRET),
    _FUTURES: (FUTURES_MAINNET_ENV_API_KEY, FUTURES_MAINNET_ENV_API_SECRET),
}
_ALL = (
    *_NAMES[_SPOT],
    *_NAMES[_FUTURES],
    FUTURES_ENV_API_KEY,
    FUTURES_ENV_API_SECRET,
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
)
_BOTH = pytest.mark.parametrize("venue", [_SPOT, _FUTURES])


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ALL:
        monkeypatch.delenv(name, raising=False)


def test_the_variable_names_are_the_ones_the_decision_names() -> None:
    assert _NAMES[_SPOT] == (
        "BINANCE_SPOT_MAINNET_API_KEY",
        "BINANCE_SPOT_MAINNET_API_SECRET",
    )
    assert _NAMES[_FUTURES] == (
        "BINANCE_FUTURES_MAINNET_API_KEY",
        "BINANCE_FUTURES_MAINNET_API_SECRET",
    )


@_BOTH
def test_both_variables_make_the_key_and_say_it_came_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, venue: TradingVenue
) -> None:
    key_name, secret_name = _NAMES[venue]
    monkeypatch.setenv(key_name, " key\n")
    monkeypatch.setenv(secret_name, "secret ")

    resolved = MainnetCredentialsProvider(InMemorySecretStore(), venue).resolve()

    assert resolved.source is CredentialsSource.ENV
    assert resolved.credentials == ExchangeCredentials("key", "secret")


@_BOTH
@pytest.mark.parametrize("which", [0, 1])
def test_half_a_pair_is_no_key(
    monkeypatch: pytest.MonkeyPatch, venue: TradingVenue, which: int
) -> None:
    monkeypatch.setenv(_NAMES[venue][which], "value")

    resolved = MainnetCredentialsProvider(InMemorySecretStore(), venue).resolve()

    assert resolved.credentials is None


@_BOTH
def test_a_whitespace_only_value_is_no_key(
    monkeypatch: pytest.MonkeyPatch, venue: TradingVenue
) -> None:
    key_name, secret_name = _NAMES[venue]
    monkeypatch.setenv(key_name, "   ")
    monkeypatch.setenv(secret_name, "secret")

    resolved = MainnetCredentialsProvider(InMemorySecretStore(), venue).resolve()

    assert resolved.source is CredentialsSource.NONE


@_BOTH
def test_a_testnet_key_is_never_a_mainnet_key(
    monkeypatch: pytest.MonkeyPatch, venue: TradingVenue
) -> None:
    for name in (
        FUTURES_ENV_API_KEY,
        FUTURES_ENV_API_SECRET,
        SPOT_ENV_API_KEY,
        SPOT_ENV_API_SECRET,
    ):
        monkeypatch.setenv(name, "testnet")

    assert (
        MainnetCredentialsProvider(InMemorySecretStore(), venue).resolve().credentials
        is None
    )


def test_a_spot_mainnet_key_is_never_the_futures_mainnet_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_NAMES[_SPOT][0], "spot")
    monkeypatch.setenv(_NAMES[_SPOT][1], "spot")

    assert (
        MainnetCredentialsProvider(InMemorySecretStore(), _FUTURES)
        .resolve()
        .credentials
        is None
    )


@pytest.mark.parametrize(
    "testnet", [TradingVenue.SPOT_TESTNET, TradingVenue.FUTURES_TESTNET]
)
def test_a_mainnet_pair_is_never_a_testnet_venues_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path, testnet: TradingVenue
) -> None:
    for names in _NAMES.values():
        monkeypatch.setenv(names[0], "mainnet")
        monkeypatch.setenv(names[1], "mainnet")
    provider = EnvFirstCredentialsProvider(
        SecretsFileSource(str(tmp_path / "none.json")), testnet
    )

    assert provider.resolve().credentials is None


# -- the keyring (D10) -------------------------------------------------------


@_BOTH
def test_a_saved_pair_is_read_from_the_store_and_says_so(venue: TradingVenue) -> None:
    store = InMemorySecretStore()
    MainnetCredentialsProvider(store, venue).save_to_file("saved-key", "saved-secret")

    resolved = MainnetCredentialsProvider(store, venue).resolve()

    assert resolved.source is CredentialsSource.KEYRING
    assert resolved.credentials == ExchangeCredentials("saved-key", "saved-secret")


def test_a_pair_saved_for_one_venue_is_not_the_other_venues() -> None:
    store = InMemorySecretStore()
    MainnetCredentialsProvider(store, _SPOT).save_to_file("k", "s")

    assert MainnetCredentialsProvider(store, _FUTURES).resolve().credentials is None


@_BOTH
def test_the_environment_wins_over_the_store(
    monkeypatch: pytest.MonkeyPatch, venue: TradingVenue
) -> None:
    store = InMemorySecretStore()
    MainnetCredentialsProvider(store, venue).save_to_file("saved", "saved")
    monkeypatch.setenv(_NAMES[venue][0], "env-key")
    monkeypatch.setenv(_NAMES[venue][1], "env-secret")

    resolved = MainnetCredentialsProvider(store, venue).resolve()

    assert resolved.source is CredentialsSource.ENV
    assert resolved.credentials == ExchangeCredentials("env-key", "env-secret")


def test_half_a_stored_pair_is_no_key() -> None:
    store = InMemorySecretStore(spot_mainnet_api_key="only-the-key")

    assert MainnetCredentialsProvider(store, _SPOT).resolve().credentials is None


@_BOTH
def test_a_machine_without_a_keyring_reads_nothing_and_refuses_to_save(
    venue: TradingVenue,
) -> None:
    provider = MainnetCredentialsProvider(UnavailableSecretStore(), venue)

    assert provider.resolve().source is CredentialsSource.NONE
    with pytest.raises(SecretStoreUnavailableError):
        provider.save_to_file("k", "s")


@_BOTH
def test_the_secret_is_never_written_to_a_file(tmp_path, venue: TradingVenue) -> None:
    store = InMemorySecretStore()
    secrets_file = tmp_path / "secrets.local.json"

    MainnetCredentialsProvider(store, venue).save_to_file("k", "s")

    assert not secrets_file.exists()
    assert set(store.secrets) == {f"{venue.value}_api_key", f"{venue.value}_api_secret"}


def test_the_store_is_read_once_not_on_every_resolve() -> None:
    reads: list[str] = []

    class _Counting(InMemorySecretStore):
        def read(self, name: str) -> str | None:
            reads.append(name)
            return super().read(name)

    provider = MainnetCredentialsProvider(_Counting(), _SPOT)

    for _ in range(5):
        provider.resolve()

    assert len(reads) == 2  # the key and the secret, once


def test_a_pair_saved_while_running_is_used_at_once() -> None:
    provider = MainnetCredentialsProvider(InMemorySecretStore(), _SPOT)
    assert provider.resolve().credentials is None

    provider.save_to_file("k", "s")

    assert provider.resolve().credentials == ExchangeCredentials("k", "s")


@_BOTH
def test_remove_stored_forgets_this_venues_key_and_not_the_other_mainnet_venue(
    venue: TradingVenue,
) -> None:
    """`BUG-176` — Remove on a venue deletes its two names from the keyring."""
    store = InMemorySecretStore()
    spot = MainnetCredentialsProvider(store, _SPOT)
    futures = MainnetCredentialsProvider(store, _FUTURES)
    spot.save_to_file("spot-key", "spot-secret")
    futures.save_to_file("futures-key", "futures-secret")
    removed, kept = (spot, futures) if venue is _SPOT else (futures, spot)

    removed.remove_stored()

    assert removed.resolve().source is CredentialsSource.NONE
    assert kept.resolve().source is CredentialsSource.KEYRING
    assert len(store.secrets) == 2
