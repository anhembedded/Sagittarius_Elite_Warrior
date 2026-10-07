"""`EPIC-034E` — the read-only mainnet key resolves from its own two variables
and from nowhere else: never a testnet pair, never `secrets.local.json`."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.mainnet_readonly_credentials import (
    MAINNET_READONLY_ENV_API_KEY,
    MAINNET_READONLY_ENV_API_SECRET,
    MainnetReadOnlyCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    FUTURES_ENV_API_KEY,
    FUTURES_ENV_API_SECRET,
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
    EnvFirstCredentialsProvider,
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

_ALL = (
    MAINNET_READONLY_ENV_API_KEY,
    MAINNET_READONLY_ENV_API_SECRET,
    FUTURES_ENV_API_KEY,
    FUTURES_ENV_API_SECRET,
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ALL:
        monkeypatch.delenv(name, raising=False)


def test_the_variable_names_are_the_ones_the_decision_names() -> None:
    assert MAINNET_READONLY_ENV_API_KEY == "BINANCE_MAINNET_READONLY_API_KEY"
    assert (
        MAINNET_READONLY_ENV_API_SECRET == "BINANCE_MAINNET_READONLY_API_SECRET"  # noqa: S105 - env var name, not a secret value
    )


def test_both_variables_make_the_key_and_say_it_came_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(MAINNET_READONLY_ENV_API_KEY, " key\n")
    monkeypatch.setenv(MAINNET_READONLY_ENV_API_SECRET, "secret ")

    resolved = MainnetReadOnlyCredentials(InMemorySecretStore()).resolve()

    assert resolved.source is CredentialsSource.ENV
    assert resolved.credentials is not None
    assert (resolved.credentials.api_key, resolved.credentials.api_secret) == (
        "key",
        "secret",
    )


@pytest.mark.parametrize(
    "present", [MAINNET_READONLY_ENV_API_KEY, MAINNET_READONLY_ENV_API_SECRET]
)
def test_half_a_pair_is_no_key(monkeypatch: pytest.MonkeyPatch, present: str) -> None:
    monkeypatch.setenv(present, "value")

    assert (
        MainnetReadOnlyCredentials(InMemorySecretStore()).resolve().credentials is None
    )


def test_a_whitespace_only_value_is_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(MAINNET_READONLY_ENV_API_KEY, "   ")
    monkeypatch.setenv(MAINNET_READONLY_ENV_API_SECRET, "secret")

    assert (
        MainnetReadOnlyCredentials(InMemorySecretStore()).resolve().source
        is CredentialsSource.NONE
    )


def test_a_testnet_key_is_never_a_mainnet_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        FUTURES_ENV_API_KEY,
        FUTURES_ENV_API_SECRET,
        SPOT_ENV_API_KEY,
        SPOT_ENV_API_SECRET,
    ):
        monkeypatch.setenv(name, "testnet")

    assert (
        MainnetReadOnlyCredentials(InMemorySecretStore()).resolve().credentials is None
    )


def test_the_mainnet_pair_is_never_the_testnet_venues_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv(MAINNET_READONLY_ENV_API_KEY, "mainnet")
    monkeypatch.setenv(MAINNET_READONLY_ENV_API_SECRET, "mainnet")
    testnet = EnvFirstCredentialsProvider(
        SecretsFileSource(str(tmp_path / "none.json")), TradingVenue.SPOT_TESTNET
    )

    assert testnet.resolve().credentials is None


# -- the keyring (D10) -------------------------------------------------------


def test_a_saved_pair_is_read_from_the_store_and_says_so() -> None:
    store = InMemorySecretStore()
    MainnetReadOnlyCredentials(store).save(
        ExchangeCredentials("saved-key", "saved-secret")
    )

    resolved = MainnetReadOnlyCredentials(store).resolve()

    assert resolved.source is CredentialsSource.KEYRING
    assert resolved.credentials == ExchangeCredentials("saved-key", "saved-secret")


def test_the_environment_wins_over_the_store(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemorySecretStore()
    MainnetReadOnlyCredentials(store).save(ExchangeCredentials("saved", "saved"))
    monkeypatch.setenv(MAINNET_READONLY_ENV_API_KEY, "env-key")
    monkeypatch.setenv(MAINNET_READONLY_ENV_API_SECRET, "env-secret")

    resolved = MainnetReadOnlyCredentials(store).resolve()

    assert resolved.source is CredentialsSource.ENV
    assert resolved.credentials == ExchangeCredentials("env-key", "env-secret")


def test_half_a_stored_pair_is_no_key() -> None:
    store = InMemorySecretStore(mainnet_readonly_api_key="only-the-key")

    assert MainnetReadOnlyCredentials(store).resolve().credentials is None


def test_a_machine_without_a_keyring_reads_nothing_and_refuses_to_save() -> None:
    credentials = MainnetReadOnlyCredentials(UnavailableSecretStore())

    assert credentials.resolve().source is CredentialsSource.NONE
    with pytest.raises(SecretStoreUnavailableError):
        credentials.save(ExchangeCredentials("k", "s"))


def test_the_secret_is_never_written_where_the_testnet_keys_are(tmp_path) -> None:
    store = InMemorySecretStore()
    secrets_file = tmp_path / "secrets.local.json"

    MainnetReadOnlyCredentials(store).save(ExchangeCredentials("k", "s"))

    assert not secrets_file.exists()
    assert set(store.secrets) == {
        "mainnet_readonly_api_key",
        "mainnet_readonly_api_secret",
    }
