"""`EPIC-010` D1 — the repo-root `state/` locator.

@details Mirrors `logs/`/`database/`'s own convention
(`app_bootstrapper.py:87-90`, `app_config.json`'s `database.dir`): kept out of
the tracked tree, resolved from `core/repo_root.py`'s `data_root()` rather than from the
process's current working directory, so it is correct regardless of where the
app was launched from.

Settled over `QStandardPaths.AppConfigLocation` for now — measured, this
application does not set `organizationName`, so that call resolves to a bare
`/root/.config` rather than an app-specific directory (`EPIC-010` design
§4.1.2). A packaged build should use it instead; that move is exactly what
`IStateStoreLocator` exists to make a one-class swap.
"""

from __future__ import annotations

import logging
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.repo_root import data_root

from ..ports.i_state_store_locator import (
    IStateStoreLocator,
)

logger = logging.getLogger("App.UiState")

_STATE_DIR_NAME = "state"
_STATE_FILE_NAME = "ui_state.json"


class RepoStateStoreLocator(IStateStoreLocator):
    """`<data root>/state/ui_state.json` — gitignored, next to `logs/` and `database/`.

    `repo_root` defaults to `data_root()` (`core/repo_root.py`): the repository
    root unless `SEW_DATA_ROOT` moves it, read at construction rather than at
    import so a test session's override applies (`EPIC-030M`).
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        root = data_root() if repo_root is None else repo_root
        self._path = root / _STATE_DIR_NAME / _STATE_FILE_NAME

    def state_file(self) -> Path:
        return self._path

    def reset(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not delete UI state file %s: %s", self._path, exc)
