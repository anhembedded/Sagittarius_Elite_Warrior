"""`EPIC-034E` (D10) — the secret store over the keyring package, on an
in-memory backend that is passed in, so the machine's real keyring is never
touched."""

from __future__ import annotations

import logging

import pytest
from keyring.backend import KeyringBackend
from keyring.backends.fail import Keyring as FailingKeyring
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.keyring_secret_store import (
    SERVICE,
    KeyringSecretStore,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    SecretStoreUnavailableError,
)


class _MemoryKeyring(KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.entries: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.entries.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.entries[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        del self.entries[(service, username)]


def test_a_written_secret_is_read_back_under_the_apps_own_service() -> None:
    backend = _MemoryKeyring()
    store = KeyringSecretStore(backend)

    store.write("name", "value")

    assert store.read("name") == "value"
    assert backend.entries == {(SERVICE, "name"): "value"}


def test_a_secret_nobody_stored_reads_as_none() -> None:
    assert KeyringSecretStore(_MemoryKeyring()).read("missing") is None


def test_a_machine_with_no_keyring_reads_none_and_says_so_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = KeyringSecretStore(FailingKeyring())

    with caplog.at_level(logging.WARNING, logger="App.MainnetReadOnly"):
        assert store.read("a") is None
        assert store.read("b") is None

    assert (
        len([r for r in caplog.records if "keyring cannot be read" in r.message]) == 1
    )


def test_a_machine_with_no_keyring_refuses_a_save_instead_of_losing_it() -> None:
    with pytest.raises(SecretStoreUnavailableError):
        KeyringSecretStore(FailingKeyring()).write("a", "b")
