"""`state/health.json`, written atomically (`EPIC-038C`, decision D5).

The snapshot is written to a temporary file beside the target, flushed to disk,
and renamed over it. A rename within one directory is atomic on both platforms
(`os.replace`), so a reader sees the previous snapshot or this one, and a
process killed between the write and the rename leaves the previous file
untouched - and a temporary file the next write replaces, never a half-written
`health.json` that `status` would call unreadable.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.health_snapshot_codec import (
    encode,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_sink import (
    IHealthSnapshotSink,
)

_TEMP_SUFFIX = ".tmp"
#: Tries at the rename, and the pause between them: about a quarter of a second.
REPLACE_ATTEMPTS = 6
REPLACE_STEP_S = 0.05


class FileHealthSnapshotSink(IHealthSnapshotSink):
    """Publishes to one file."""

    def __init__(
        self,
        path: Path,
        replace: Callable[[Path, Path], object] = os.replace,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._path = path
        #: The rename; injected so a test can stop the process "between the
        #: write and the rename" without killing the test runner.
        self._replace = replace
        self._sleep = sleep

    def publish(self, snapshot: HealthSnapshot) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_name(self._path.name + _TEMP_SUFFIX)
        text = json.dumps(encode(snapshot), indent=2, sort_keys=True)
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        self._replace_tolerating_a_reader(temporary)

    def _replace_tolerating_a_reader(self, temporary: Path) -> None:
        """On Windows a rename over a file another process holds open (a
        `status --watch` reading at this instant) is refused with
        `PermissionError`. The reader lets go in milliseconds, so the rename is
        tried again a few times; only a refusal that outlasts them is raised
        (and `HealthPublishing` logs it)."""
        for _ in range(REPLACE_ATTEMPTS - 1):
            try:
                self._replace(temporary, self._path)
            except PermissionError:
                self._sleep(REPLACE_STEP_S)
            else:
                return
        self._replace(temporary, self._path)
