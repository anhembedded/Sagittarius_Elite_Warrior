"""`ISecretStore` doubles for tests: an in-memory one, and one that cannot be used."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)


class InMemorySecretStore(ISecretStore):
    def __init__(self, **secrets: str) -> None:
        self.secrets = dict(secrets)

    def read(self, name: str) -> str | None:
        return self.secrets.get(name)

    def write(self, name: str, value: str) -> None:
        self.secrets[name] = value

    def delete(self, name: str) -> None:
        self.secrets.pop(name, None)


class UnavailableSecretStore(ISecretStore):
    """A machine with no usable keyring: reads find nothing, saves refuse."""

    def read(self, name: str) -> str | None:
        return None

    def write(self, name: str, value: str) -> None:
        raise SecretStoreUnavailableError("no keyring here")

    def delete(self, name: str) -> None:
        raise SecretStoreUnavailableError("no keyring here")
