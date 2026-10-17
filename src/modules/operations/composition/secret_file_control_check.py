"""The permission rule for command files, borrowed from the secret files' (`EPIC-038J`).

A command file is believed on the same terms as a key file: owner-only, owned by the account the
host runs as, in a directory nobody else can write to (POSIX), or an ACL of the service account
and the administrators (Windows). `EPIC-038E` built and reviewed those checks; this adapter
lends them to the inbox through the port `operations` owns. It lives in `composition/`, the one
place of a module that may import `support/secrets`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_control_file_check import (
    IControlFileCheck,
)
from Sagittarius_Elite_Warrior.src.support.secrets.adapters.posix_secret_file_permission_check import (
    PosixSecretFilePermissionCheck,
)
from Sagittarius_Elite_Warrior.src.support.secrets.adapters.windows_secret_file_permission_check import (
    WindowsSecretFilePermissionCheck,
)
from Sagittarius_Elite_Warrior.src.support.secrets.contracts.i_secret_file_check import (
    ISecretFileCheck,
)


class SecretFileControlCheck(IControlFileCheck):
    def __init__(self, check: ISecretFileCheck) -> None:
        self._check = check

    def inspect(self, path: Path, descriptor: int) -> str:
        verdict = self._check.inspect(path, descriptor)
        return "" if verdict.accepted else verdict.problem


def platform_control_file_check() -> IControlFileCheck:
    """The rule of this operating system."""
    return SecretFileControlCheck(
        WindowsSecretFilePermissionCheck()
        if sys.platform == "win32"
        else PosixSecretFilePermissionCheck()
    )
