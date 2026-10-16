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
started is refused from then on. The file is opened once, without following a
symbolic link, and the checks and the read use that one descriptor.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import (
    ISecretStore,
    SecretStoreUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.secrets.contracts.i_secret_file_check import (
    ISecretFileCheck,
)
from Sagittarius_Elite_Warrior.src.support.secrets.secret_file_name import (
    MAX_SECRET_BYTES,
    file_in,
    secret_from_bytes,
)

logger = logging.getLogger("App.Credentials")

#: Never follow a symbolic link: a link to any file the service can read would make
#: that file a secret file. `O_NOFOLLOW` is absent on Windows, where a link needs a
#: privilege to create and the ACL check reads the link's target.
_OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_BINARY", 0)
    # A named pipe opened for reading blocks until a writer appears, before any check
    # could refuse it; without blocking it opens at once and is refused as "not a
    # regular file". Harmless on a regular file.
    | getattr(os, "O_NONBLOCK", 0)
)

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
        if path is None:
            return None
        try:
            descriptor = os.open(path, _OPEN_FLAGS)
        except FileNotFoundError:
            return None
        except OSError as exc:
            # A symbolic link (O_NOFOLLOW) or a file the service cannot open.
            self._log_once(
                name,
                "The secret file %s was not read: it cannot be opened (%s), and a "
                "symbolic link is never followed [secret-file]",
                path,
                type(exc).__name__,
            )
            return None
        # One descriptor serves the checks and the read, so the file judged is the
        # file read even if the path is replaced in between.
        with os.fdopen(descriptor, "rb") as opened:
            for check in self._checks:
                verdict = check.inspect(path, opened.fileno())
                if not verdict.accepted:
                    self._log_once(
                        name,
                        "The secret file %s was not read: %s. To fix it: %s [secret-file]",
                        path,
                        verdict.problem,
                        verdict.fix,
                    )
                    return None
            return self._text_of(name, path, opened)

    def _text_of(self, name: str, path: Path, opened: BinaryIO) -> str | None:
        try:
            raw = opened.read(MAX_SECRET_BYTES + 1)
            if len(raw) > MAX_SECRET_BYTES:
                reason = "it is too large to be a secret"
            else:
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
