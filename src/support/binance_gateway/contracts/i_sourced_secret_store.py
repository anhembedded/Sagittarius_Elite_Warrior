"""`EPIC-038E` — a secret store that says which of its backends answered.

@details A mainnet key can come from several places (systemd credentials, a
permission-checked file, the keyring). The provider that resolves it must name the
place - a status page and `preflight` show it - without ever showing the value, so
this port adds to `ISecretStore` the reads that return the backend with the value.
The value is excluded from every `repr`: a traceback, a log line or an assertion
diff that prints one of these shows the source only.

A pair is read from **one backend**: a key from one place and its secret from
another would be a mismatch the exchange rejects, or worse, accepts for another
account.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import ISecretStore
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)


@dataclass(frozen=True)
class SourcedSecret:
    value: str = field(repr=False)
    source: CredentialsSource


@dataclass(frozen=True)
class SourcedPair:
    first: str = field(repr=False)
    second: str = field(repr=False)
    source: CredentialsSource


class ISourcedSecretStore(ISecretStore):
    @abstractmethod
    def read_sourced(self, name: str) -> SourcedSecret | None:
        """The secret called `name` and the backend that held it, or `None`."""

    @abstractmethod
    def read_pair(self, first: str, second: str) -> SourcedPair | None:
        """Both secrets from the first backend that holds both, or `None`."""

    @abstractmethod
    def read_from_writer(self, name: str) -> str | None:
        """What the app's own writable backend holds under `name`, ignoring the
        provisioned ones: what a failed save must put back, never a copy of a
        secret the operator keeps elsewhere."""
