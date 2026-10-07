"""`EPIC-034E` (D10) — where a secret is kept so that it never sits in a file.

@details A named secret in, a string out. The one implementation is the
operating system's keyring (`KeyringSecretStore`); the port exists so the
credentials that read it are tested without one, and so a store that is not
available is a named condition rather than a swallowed error.

Plausible extensions, each one implementation: an encrypted file for a
machine with no keyring (a decision of its own: D10 chose the keyring over a
file); a test store.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SecretStoreUnavailableError(RuntimeError):
    """The store cannot be used here (a headless machine with no keyring
    backend, a locked keyring). Reading treats it as "nothing stored"; saving
    refuses, and says why."""


class ISecretStore(ABC):
    @abstractmethod
    def read(self, name: str) -> str | None:
        """The secret called `name`, or `None` when none is stored or the
        store cannot be used (the reason is logged once)."""

    @abstractmethod
    def write(self, name: str, value: str) -> None:
        """Stores `value` under `name`, replacing any earlier one.
        @raise SecretStoreUnavailableError The store cannot be used."""
