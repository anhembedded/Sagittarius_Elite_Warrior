"""Write a JSON checkpoint so a crash leaves the previous file whole.

@details The text goes to a temporary file in the same directory, is flushed to disk, then
`Path.replace()`d over the target; the temporary file is removed whatever happens. Both owner
checkpoint adapters (`JsonOwnerInventoryCheckpoints`, `JsonOwnerPositionCheckpoints`) write
through it, so a correction to the way a checkpoint is made durable is made once.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_TEMP_SUFFIX = ".json.tmp"


def write_json_atomically(target: Path, payload: dict[str, Any]) -> None:
    """@brief `payload` as the whole content of `target`, or nothing changed.
    @throws OSError The directory cannot be made or the file written."""
    text = json.dumps(payload, indent=2, sort_keys=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_suffix(_TEMP_SUFFIX)
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(target)
    finally:
        temp_path.unlink(missing_ok=True)
