"""`EPIC-038E` — the stores in one order: the first that holds a secret answers,
and says which one it was; a pair is never assembled from two backends."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.ordered_secret_stores import (
    OrderedSecretStores,
    SecretBackend,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    MainnetCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)

_SPOT = TradingVenue.SPOT_MAINNET
KEY, SECRET = "spot_mainnet_api_key", "spot_mainnet_api_secret"


def _order(*backends: SecretBackend) -> OrderedSecretStores:
    return OrderedSecretStores(backends)


def test_the_first_store_that_holds_a_secret_answers() -> None:
    first = InMemorySecretStore()
    second = InMemorySecretStore(**{KEY: "from-second"})
    third = InMemorySecretStore(**{KEY: "from-third"})
    order = _order(
        SecretBackend(CredentialsSource.SYSTEMD_CREDENTIAL, first),
        SecretBackend(CredentialsSource.SECRET_FILE, second),
        SecretBackend(CredentialsSource.KEYRING, third, writable=True),
    )

    assert order.read(KEY) == "from-second"


def test_a_secret_no_store_holds_reads_none() -> None:
    order = _order(SecretBackend(CredentialsSource.KEYRING, InMemorySecretStore()))

    assert order.read_pair(KEY, SECRET) is None
    assert order.read(KEY) is None


def test_a_new_store_joins_by_one_entry_in_the_order() -> None:
    held = InMemorySecretStore(**{KEY: "k", SECRET: "s"})
    before = _order(SecretBackend(CredentialsSource.KEYRING, InMemorySecretStore()))
    after = _order(
        SecretBackend(CredentialsSource.SECRET_FILE, held),
        *before.backends,
    )

    assert before.read(KEY) is None
    assert after.read(KEY) == "k"
    # The provider needed no edit to learn of it.
    resolved = MainnetCredentialsProvider(after, _SPOT).resolve()
    assert resolved.source is CredentialsSource.SECRET_FILE


def test_a_pair_comes_whole_from_the_first_store_that_holds_both() -> None:
    half = InMemorySecretStore(**{KEY: "half-key"})
    whole = InMemorySecretStore(**{KEY: "whole-key", SECRET: "whole-secret"})
    order = _order(
        SecretBackend(CredentialsSource.SYSTEMD_CREDENTIAL, half),
        SecretBackend(CredentialsSource.KEYRING, whole, writable=True),
    )

    pair = order.read_pair(KEY, SECRET)

    assert pair is not None
    assert (pair.first, pair.second, pair.source) == (
        "whole-key",
        "whole-secret",
        CredentialsSource.KEYRING,
    )


def test_a_key_in_one_store_and_its_secret_in_another_is_no_pair() -> None:
    order = _order(
        SecretBackend(
            CredentialsSource.SYSTEMD_CREDENTIAL, InMemorySecretStore(**{KEY: "k"})
        ),
        SecretBackend(CredentialsSource.KEYRING, InMemorySecretStore(**{SECRET: "s"})),
    )

    assert order.read_pair(KEY, SECRET) is None


def test_writes_and_deletes_go_to_the_one_writable_store() -> None:
    provisioned = InMemorySecretStore()
    keyring = InMemorySecretStore()
    order = _order(
        SecretBackend(CredentialsSource.SYSTEMD_CREDENTIAL, provisioned),
        SecretBackend(CredentialsSource.KEYRING, keyring, writable=True),
    )

    order.write(KEY, "saved")
    assert keyring.secrets == {KEY: "saved"}
    assert provisioned.secrets == {}

    order.delete(KEY)
    assert keyring.secrets == {}


def test_with_no_writable_store_a_write_refuses_and_says_who_provisions_keys() -> None:
    order = _order(
        SecretBackend(CredentialsSource.SYSTEMD_CREDENTIAL, InMemorySecretStore())
    )

    for attempt in (lambda: order.write(KEY, "v"), lambda: order.delete(KEY)):
        with pytest.raises(SecretStoreUnavailableError, match="outside the app"):
            attempt()


def test_an_unavailable_writer_refuses_as_the_store_does() -> None:
    order = _order(
        SecretBackend(
            CredentialsSource.KEYRING, UnavailableSecretStore(), writable=True
        )
    )

    with pytest.raises(SecretStoreUnavailableError, match="no keyring"):
        order.write(KEY, "v")


def test_a_single_store_is_the_keyring_and_writable() -> None:
    store = InMemorySecretStore()
    order = OrderedSecretStores.single(store)

    order.write(KEY, "v")

    assert order.read(KEY) == "v"
    assert store.secrets == {KEY: "v"}


def test_the_values_are_not_in_the_repr_of_a_pair_a_read_returns() -> None:
    order = OrderedSecretStores.single(
        InMemorySecretStore(**{KEY: "distinctive-key", SECRET: "distinctive-secret"})
    )
    pair = order.read_pair(KEY, SECRET)

    assert pair is not None
    for shown in (repr(pair), str(pair), repr(order), repr(order.backends)):
        assert "distinctive-key" not in shown
        assert "distinctive-secret" not in shown


def test_the_provider_reports_the_source_that_served_the_key() -> None:
    order = _order(
        SecretBackend(
            CredentialsSource.SYSTEMD_CREDENTIAL,
            InMemorySecretStore(**{KEY: "k", SECRET: "s"}),
        ),
        SecretBackend(CredentialsSource.KEYRING, InMemorySecretStore(), writable=True),
    )

    resolved = MainnetCredentialsProvider(order, _SPOT).resolve()

    assert resolved.source is CredentialsSource.SYSTEMD_CREDENTIAL
    assert resolved.credentials is not None
    assert resolved.credentials.api_key == "k"


@pytest.mark.parametrize(
    ("source", "provisioned_outside"),
    [
        (CredentialsSource.ENV, True),
        (CredentialsSource.SYSTEMD_CREDENTIAL, True),
        (CredentialsSource.SECRET_FILE, True),
        (CredentialsSource.KEYRING, False),
        (CredentialsSource.FILE, False),
        (CredentialsSource.NONE, False),
    ],
)
def test_a_key_provisioned_outside_the_app_is_never_offered_for_editing(
    source: CredentialsSource, provisioned_outside: bool
) -> None:
    assert source.is_provisioned_outside_the_app is provisioned_outside
