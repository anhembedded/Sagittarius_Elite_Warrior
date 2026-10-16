"""`EPIC-038E` — the secret stores in one order, and which of them answered.

@details A mainnet key can be given to the app in more than one way (systemd
credentials, a permission-checked file, the operating system's keyring). They sit
in this list in the order they are asked; the first that holds the secret answers
and is named, so a status page and `preflight` can say where a key came from
without ever saying what it is. Adding a way to provision a key is one class
behind `ISecretStore` and one `SecretBackend` in the order list
(`secret_store_order.py`, beside this file); nothing here changes.

The list is itself an `ISecretStore` (and an `ISourcedSecretStore`, the port the
provider reads), so what only needs to read or save a secret takes it as it takes
any store. Writes and deletes
go to the one backend marked writable (the keyring): the others are provisioned by
the operator and their stores refuse a write in their own words.

A key and its secret are read as a **pair from one backend**: a key from one place
and a secret from another is a mismatch the exchange would reject, or worse, accept
for another account.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_sourced_secret_store import (
    ISourcedSecretStore,
    SourcedPair,
)


@dataclass(frozen=True)
class SecretBackend:
    source: CredentialsSource
    store: ISecretStore
    #: The app may save to and remove from this one (the keyring).
    writable: bool = False


class OrderedSecretStores(ISourcedSecretStore):
    def __init__(self, backends: Sequence[SecretBackend]) -> None:
        self._backends = tuple(backends)

    @classmethod
    def single(cls, store: ISecretStore) -> OrderedSecretStores:
        """One writable store, named as the keyring: what a test or a machine with
        no other way to provision a key has."""
        return cls((SecretBackend(CredentialsSource.KEYRING, store, writable=True),))

    @property
    def backends(self) -> tuple[SecretBackend, ...]:
        return self._backends

    def read_pair(self, first: str, second: str) -> SourcedPair | None:
        """Both secrets from the first backend that holds both."""
        for backend in self._backends:
            one = backend.store.read(first)
            other = backend.store.read(second)
            if one is not None and other is not None:
                return SourcedPair(one, other, backend.source)
        return None

    def read_from_writer(self, name: str) -> str | None:
        """What the app's own store holds under `name`, ignoring the provisioned
        ones: what a failed save must put back, and never a copy of a secret the
        operator keeps elsewhere."""
        for backend in self._backends:
            if backend.writable:
                return backend.store.read(name)
        return None

    def read(self, name: str) -> str | None:
        for backend in self._backends:
            value = backend.store.read(name)
            if value is not None:
                return value
        return None

    def write(self, name: str, value: str) -> None:
        self._writer().write(name, value)

    def delete(self, name: str) -> None:
        self._writer().delete(name)

    def _writer(self) -> ISecretStore:
        for backend in self._backends:
            if backend.writable:
                return backend.store
        raise SecretStoreUnavailableError(
            "no store here can be saved to: a key is provisioned outside the app "
            "(the service unit's credentials or a secret file)"
        )

    def __repr__(self) -> str:
        sources = ", ".join(b.source.value for b in self._backends)
        return f"{type(self).__name__}({sources})"
