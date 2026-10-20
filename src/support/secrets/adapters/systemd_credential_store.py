"""`EPIC-038E` (O3) — `ISecretStore` over systemd credentials.

@details The unit has one line, `LoadCredential=sew:/etc/sew/credentials`. Given a
directory, systemd loads every regular file in it as a credential named
`<ID>_<file name>` (systemd.exec(5), `LoadCredential=`, since systemd 251), so the file
`/etc/sew/credentials/spot_mainnet_api_key` is found at
`$CREDENTIALS_DIRECTORY/sew_spot_mainnet_api_key`. A file that does not exist is simply not
a credential: a venue or feature without its file is off and the host still starts, where
a `LoadCredential=` line per file made systemd refuse the start (`243/CREDENTIALS`).
Unlike an environment variable the value is not inherited by child processes, and the
kernel checks access on each read (`systemd.io/CREDENTIALS`). The secret's name is the
file's name: `<venue>_api_key` and `<venue>_api_secret`, and each alert channel's own name.

A credential named without the prefix, `$CREDENTIALS_DIRECTORY/spot_mainnet_api_key`, is read
too, when the prefixed one is absent: that is what a unit with one `LoadCredential=` line
per file (the layout before this one) hands the process, so an install that has the new
code and not yet the new unit keeps its keys.

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
from Sagittarius_Elite_Warrior.src.support.secrets.secret_file_name import (
    MAX_SECRET_BYTES,
    file_in,
    secret_from_bytes,
)

logger = logging.getLogger("App.Credentials")

CREDENTIALS_DIRECTORY_ENV = "CREDENTIALS_DIRECTORY"

#: The ID of the unit's `LoadCredential=<ID>:<directory>`; systemd names each file `<ID>_<file>`.
#: `scripts/render_service_files.py` writes the unit from this, so the two cannot differ.
UNIT_CREDENTIAL_ID = "sew"


def unit_credential_name(secret_name: str) -> str:
    """The name systemd gives the credential it loads from the file `secret_name`."""
    return f"{UNIT_CREDENTIAL_ID}_{secret_name}"


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
        if not directory:
            return None
        try:
            path = self._credential_file(Path(directory), name)
            if path is None:
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

    @staticmethod
    def _credential_file(directory: Path, name: str) -> Path | None:
        """The file holding `name`: the unit's prefixed credential first, then the bare name."""
        if (
            file_in(directory, name) is None
        ):  # not a plain file name: the prefix would hide it
            return None
        for file_name in (unit_credential_name(name), name):
            path = directory / file_name
            if path.is_file():
                return path
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
