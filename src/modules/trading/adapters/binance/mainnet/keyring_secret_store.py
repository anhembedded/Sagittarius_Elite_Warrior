"""`EPIC-034E` (D10) — `ISecretStore` over the operating system's keyring
(Windows Credential Manager, macOS Keychain, Secret Service on Linux), through
the `keyring` package.

@details One service name, one entry per secret name. `read` never raises: a
machine with no usable backend (a headless server, a locked keyring) reads as
"nothing stored", logged once at INFO, and the environment variables remain the way to
give the key. `write` raises `SecretStoreUnavailableError` instead, because a
save that silently went nowhere would let the owner believe a key was kept.

The backend is injectable (`keyring.backend.KeyringBackend`) so a test runs on
an in-memory one without touching the machine's real keyring.
"""

from __future__ import annotations

import logging

import keyring
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)

logger = logging.getLogger("App.Keyring")

SERVICE = "Sagittarius_Elite_Warrior"


class KeyringSecretStore(ISecretStore):
    def __init__(self, backend: KeyringBackend | None = None) -> None:
        self._backend = backend
        self._unavailable_logged = False

    def read(self, name: str) -> str | None:
        try:
            return self._keyring().get_password(SERVICE, name)
        except KeyringError as exc:
            self._log_unavailable(exc)
            return None

    def write(self, name: str, value: str) -> None:
        try:
            self._keyring().set_password(SERVICE, name, value)
        except KeyringError as exc:
            raise SecretStoreUnavailableError(
                f"the operating system's keyring cannot store a secret here: {exc}"
            ) from exc

    def _keyring(self) -> KeyringBackend:
        return self._backend if self._backend is not None else keyring.get_keyring()

    def _log_unavailable(self, exc: KeyringError) -> None:
        if not self._unavailable_logged:
            self._unavailable_logged = True
            # INFO, not WARNING: a headless machine (CI, a server) has no keyring and
            # reading the venues' keys is ordinary there; the environment variables
            # are the way, and the run-log scan would fail every such run.
            logger.info(
                "The operating system's keyring cannot be read (%s); a mainnet "
                "key is read from the environment only [keyring]",
                exc,
            )
