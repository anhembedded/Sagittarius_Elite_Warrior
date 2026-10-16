"""`EPIC-038E` — the one place the order of the secret stores is written.

@details A mainnet key is looked up **environment first** (the provider's own
rule), then in this list, in this order:

| # | Store | Source it reports | Present when |
| :-: | :--- | :--- | :--- |
| 1 | systemd credentials (`$CREDENTIALS_DIRECTORY`) | `systemd-credential` | always (it reads nothing without the variable) |
| 2 | permission-checked files | `secret-file` | `SEW_SECRET_FILES_DIR` names a directory |
| 3 | the operating system's keyring | `keyring` | always; the only one the app writes to |

A way to provision a key that the operator does best is above the keyring, so a
unit file that names a key is not shadowed by an older one a person saved in a
desktop session. Adding a store is one `_Entry` below and its class; the provider,
the enrolment and the pre-flight read the order and change nothing.

The Windows Credential Manager under a service account is the keyring entry here
and is **unverified** on a real service (`EPIC-038E`): the file store is the
fallback O3 names.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import ISecretStore
from Sagittarius_Elite_Warrior.src.core.repo_root import repo_root
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.secrets.adapters.keyring_secret_store import (
    KeyringSecretStore,
)
from Sagittarius_Elite_Warrior.src.support.secrets.adapters.permission_checked_file_store import (
    PermissionCheckedFileStore,
)
from Sagittarius_Elite_Warrior.src.support.secrets.adapters.posix_secret_file_permission_check import (
    PosixSecretFilePermissionCheck,
)
from Sagittarius_Elite_Warrior.src.support.secrets.adapters.secret_file_placement_check import (
    SecretFilePlacementCheck,
)
from Sagittarius_Elite_Warrior.src.support.secrets.adapters.systemd_credential_store import (
    SystemdCredentialStore,
)
from Sagittarius_Elite_Warrior.src.support.secrets.adapters.windows_secret_file_permission_check import (
    WindowsSecretFilePermissionCheck,
)
from Sagittarius_Elite_Warrior.src.support.secrets.contracts.i_secret_file_check import (
    ISecretFileCheck,
)
from Sagittarius_Elite_Warrior.src.support.secrets.ordered_secret_stores import (
    OrderedSecretStores,
    SecretBackend,
)

#: The directory of secret files; unset or empty means there is no file store.
SECRET_FILES_DIRECTORY_ENV = "SEW_SECRET_FILES_DIR"  # noqa: S105 - an environment variable's name, not a secret


@dataclass(frozen=True)
class _Entry:
    source: CredentialsSource
    #: The store for this environment, or `None` when it is not configured here.
    build: Callable[[Mapping[str, str]], ISecretStore | None]
    writable: bool = False


def _systemd(environ: Mapping[str, str]) -> ISecretStore:
    return SystemdCredentialStore(environ)


def _secret_files(environ: Mapping[str, str]) -> ISecretStore | None:
    directory = environ.get(SECRET_FILES_DIRECTORY_ENV, "")
    if not directory:
        return None
    permission: ISecretFileCheck = (
        WindowsSecretFilePermissionCheck()
        if sys.platform == "win32"
        else PosixSecretFilePermissionCheck()
    )
    return PermissionCheckedFileStore(
        Path(directory), (SecretFilePlacementCheck(repo_root()), permission)
    )


def _keyring(environ: Mapping[str, str]) -> ISecretStore:
    return KeyringSecretStore()


#: The order. One line per store.
_ORDER = (
    _Entry(CredentialsSource.SYSTEMD_CREDENTIAL, _systemd),
    _Entry(CredentialsSource.SECRET_FILE, _secret_files),
    _Entry(CredentialsSource.KEYRING, _keyring, writable=True),
)


def build_secret_stores(
    environ: Mapping[str, str] | None = None,
) -> OrderedSecretStores:
    """The stores that exist in `environ` (the process environment by default), in order."""
    seen = environ if environ is not None else os.environ
    backends = []
    for entry in _ORDER:
        store = entry.build(seen)
        if store is not None:
            backends.append(SecretBackend(entry.source, store, entry.writable))
    return OrderedSecretStores(backends)
