"""Read `state/health.json` (`EPIC-038C`): what a second process learns of a host."""

from __future__ import annotations

import json
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.health_snapshot_codec import (
    decode,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.health_snapshot import (
    HealthSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_health_snapshot_source import (
    HealthSnapshotUnreadableError,
    IHealthSnapshotSource,
)


class FileHealthSnapshotSource(IHealthSnapshotSource):
    """Reads one file; never writes."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> HealthSnapshot | None:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise HealthSnapshotUnreadableError(
                f"{self._path} cannot be read: {exc.strerror or exc!r}"
            ) from exc
        try:
            document = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HealthSnapshotUnreadableError(
                f"{self._path} is not valid JSON: {exc.msg}"
            ) from exc
        return decode(document)
