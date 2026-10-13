"""`EPIC-038E` (O3) — `ISecretStore` over systemd credentials.

@details A unit with `LoadCredential=spot_mainnet_api_key:/etc/sew/spot_key` finds
the file at `$CREDENTIALS_DIRECTORY/spot_mainnet_api_key`. Unlike an environment
variable the value is not inherited by child processes, and the kernel checks
access on each read (`systemd.io/CREDENTIALS`). The secret's name is the
credential's name, so the unit file lists the names `<venue>_api_key` and
`<venue>_api_secret`.

The app reads and never writes: a credential is provisioned by the unit file, so
`write` and `delete` refuse and say so. A machine without systemd, or a process not
started by a unit, has no `$CREDENTIALS_DIRECTORY` and reads "nothing stored" with
no log line: that is the desktop's ordinary state, not a fault.

The directory is read at each call (no cache): the file is local and small, and a
rotated credential is picked up by the next read.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.secret_file_name import (
    MAX_SECRET_BYTES,
    file_in,
    secret_from_bytes,
)

logger = logging.getLogger("App.Credentials")

CREDENTIALS_DIRECTORY_ENV = "CREDENTIALS_DIRECTORY"

_PROVISIONED_BY_THE_UNIT = (
    "systemd credentials are provisioned by the service's unit file "
    "(LoadCredential=), not by the app"
)


class SystemdCredentialStore(ISecretStore):
    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ
        self._unreadable_logged: set[str] = set()

    def read(self, name: str) -> str | None:
        directory = self._environ.get(CREDENTIALS_DIRECTORY_ENV, "")
        path = file_in(Path(directory), name) if directory else None
        if path is None:
            return None
        try:
            if not path.is_file():
                return None
            raw = path.read_bytes()
            if len(raw) > MAX_SECRET_BYTES:
                self._log_unreadable(name, "it is too large to be a secret")
                return None
            return secret_from_bytes(raw)
        except UnicodeDecodeError:
            self._log_unreadable(name, "it is not text")  # the error would quote bytes
        except OSError as exc:
            self._log_unreadable(name, type(exc).__name__)
        return None

    def write(self, name: str, value: str) -> None:
        raise SecretStoreUnavailableError(_PROVISIONED_BY_THE_UNIT)

    def delete(self, name: str) -> None:
        raise SecretStoreUnavailableError(_PROVISIONED_BY_THE_UNIT)

    def _log_unreadable(self, name: str, why: str) -> None:
        if name in self._unreadable_logged:
            return
        self._unreadable_logged.add(name)
        logger.warning(
            "The systemd credential %r cannot be read: %s [systemd-credential]",
            name,
            why,
        )
