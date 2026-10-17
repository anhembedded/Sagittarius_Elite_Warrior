"""The command directory itself: where it is, what its files are called, and that it is private (`EPIC-038J`).

`<data root>/state/control/` holds `cmd-<id>.json` (a command waiting for the host) and
`audit.jsonl` (the host's record). Both halves of control - the host that reads and the
operator's process that writes - name them through here, so neither can drift from the other.

**Private means owner-only.** On POSIX the directory is `0700`, owned by the account the host
runs as; a file is believed only if it is the same account's and `0600` (the checks `EPIC-038E`
built, applied by the inbox). The host creates the directory when `run` starts and tightens one
it already owns; a directory owned by someone else is a reason to offer no control at all.
**Known limit, Windows:** `chmod` does nothing there; the directory inherits the ACL of
`state/`, and the ACL check on each file is what keeps another account's command out.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

CONTROL_DIRECTORY_NAME = "control"
AUDIT_FILE_NAME = "audit.jsonl"

_COMMAND_FILE = re.compile(r"^cmd-[0-9a-f]{32}\.json$")
_PRIVATE_MODE = 0o700


def control_directory_of(state_directory: Path) -> Path:
    return state_directory / CONTROL_DIRECTORY_NAME


def command_file_name(command_id: str) -> str:
    return f"cmd-{command_id}.json"


def is_command_file_name(name: str) -> bool:
    return bool(_COMMAND_FILE.fullmatch(name))


def prepare_private_directory(directory: Path) -> str:
    """Make `directory` exist and be private to this account; the problem in words, or `""`.

    A directory this account does not own is never adopted."""
    try:
        directory.mkdir(parents=True, mode=_PRIVATE_MODE, exist_ok=True)
        found = directory.stat()
    except OSError as failure:
        return f"{directory} cannot be created or read ({type(failure).__name__})"
    if not stat.S_ISDIR(found.st_mode):
        return f"{directory} is not a directory"
    if not hasattr(os, "geteuid"):
        return ""
    if found.st_uid != os.geteuid():
        return f"{directory} is owned by another account, so it is not trusted"
    if stat.S_IMODE(found.st_mode) != _PRIVATE_MODE:
        try:
            directory.chmod(_PRIVATE_MODE)
        except OSError as failure:
            return f"{directory} could not be made private ({type(failure).__name__})"
    return ""
