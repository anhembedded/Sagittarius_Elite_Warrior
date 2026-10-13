"""`EPIC-038E` (O3) — `ISecretStore` over a directory of owner-only files.

@details For a server with neither systemd credentials nor a keyring (a Windows
service account, a container): the operator puts one file per secret, named
`<venue>_api_key` and `<venue>_api_secret`, in a directory they name with
`SEW_SECRET_FILES_DIR`. The app reads a file only when **every check accepts it**
(`ISecretFileCheck`): owner-only and owned by the running user on POSIX, an ACL of
the service account and the administrators on Windows, and a place outside the
repository and any git work tree that does not ignore it. The protection is the
operating system's permission alone - the secret is unencrypted at rest.

A refused file reads "nothing stored" and is logged once at WARNING, saying what
is wrong and the command that fixes it, never the file's contents. The app does
not write the files: `write` and `delete` refuse.

Checks run at each read, not once: a file made world-readable after the app
started is refused from then on.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_secret_file_check import (
    ISecretFileCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.secret_file_name import (
    MAX_SECRET_BYTES,
    file_in,
    secret_from_bytes,
)

logger = logging.getLogger("App.Credentials")

_PROVISIONED_BY_THE_OPERATOR = (
    "secret files are provisioned by the operator, not by the app: put the file "
    "in the secret files directory with owner-only permission"
)


class PermissionCheckedFileStore(ISecretStore):
    def __init__(self, directory: Path, checks: Sequence[ISecretFileCheck]) -> None:
        self._directory = directory
        self._checks = tuple(checks)
        self._refusal_logged: set[str] = set()

    def read(self, name: str) -> str | None:
        path = file_in(self._directory, name)
        if path is None or not path.is_file():
            return None
        for check in self._checks:
            verdict = check.inspect(path)
            if not verdict.accepted:
                self._log_once(
                    name,
                    "The secret file %s was not read: %s. To fix it: %s [secret-file]",
                    path,
                    verdict.problem,
                    verdict.fix,
                )
                return None
        try:
            raw = path.read_bytes()
            if len(raw) > MAX_SECRET_BYTES:
                self._log_once(
                    name,
                    "The secret file %s was not read: %s [secret-file]",
                    path,
                    "it is too large to be a secret",
                )
                return None
            return secret_from_bytes(raw)
        except UnicodeDecodeError:
            reason = "it is not text"  # the error would quote bytes
        except OSError as exc:
            reason = type(exc).__name__
        self._log_once(
            name, "The secret file %s was not read: %s [secret-file]", path, reason
        )
        return None

    def write(self, name: str, value: str) -> None:
        raise SecretStoreUnavailableError(_PROVISIONED_BY_THE_OPERATOR)

    def delete(self, name: str) -> None:
        raise SecretStoreUnavailableError(_PROVISIONED_BY_THE_OPERATOR)

    def _log_once(self, name: str, message: str, *args: object) -> None:
        if name in self._refusal_logged:
            return
        self._refusal_logged.add(name)
        logger.warning(message, *args)
