"""The repository root, found by its landmark.

@details `pyproject.toml` marks the root; the search walks up from this
file, so it is correct wherever the app was launched from and wherever this
file moves (`test_no_root_is_found_by_counting.py` refuses counting parent
directories). Shared by the modules that keep files under the gitignored
`<repo root>/state/`: `bots` (its store) and `trading` (its inventory
checkpoints).
"""

from __future__ import annotations

from pathlib import Path

_LANDMARK = "pyproject.toml"


def repo_root() -> Path:
    """The directory holding `pyproject.toml`, searching up from this file."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / _LANDMARK).is_file():
            return candidate
    raise FileNotFoundError(f"No {_LANDMARK} above {__file__}")
