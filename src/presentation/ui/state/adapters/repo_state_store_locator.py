"""`EPIC-010` D1 — the repo-root `state/` locator.

@details Mirrors `logs/`/`database/`'s own convention
(`app_bootstrapper.py:87-90`, `app_config.json`'s `database.dir`): kept out of
the tracked tree, resolved relative to this file rather than to the process's
current working directory, so it is correct regardless of where the app was
launched from.

Settled over `QStandardPaths.AppConfigLocation` for now — measured, this
application does not set `organizationName`, so that call resolves to a bare
`/root/.config` rather than an app-specific directory (`EPIC-010` design
§4.1.2). A packaged build should use it instead; that move is exactly what
`IStateStoreLocator` exists to make a one-class swap.
"""

from __future__ import annotations

import logging
from pathlib import Path

from Sagittarius_Elite_Warrior.src.presentation.ui.state.ports.i_state_store_locator import (
    IStateStoreLocator,
)

logger = logging.getLogger("App.UiState")

_STATE_DIR_NAME = "state"
_STATE_FILE_NAME = "ui_state.json"

#: `.parents[5]` from this file's own directory (`adapters/`) reaches the repo
#: root: adapters -> state -> ui -> presentation -> src -> repo root. Verified
#: directly rather than derived by counting `os.path.dirname()` calls the way
#: `app_bootstrapper.py:87-90` does it — that file lives two directories
#: shallower (`presentation/ui/`), so its "4 dirname calls" is not this file's
#: answer, and guessing by analogy is exactly how an off-by-one gets shipped.
_REPO_ROOT = Path(__file__).resolve().parents[5]


class RepoStateStoreLocator(IStateStoreLocator):
    """`<repo root>/state/ui_state.json` — gitignored, next to `logs/` and `database/`."""

    def __init__(self, repo_root: Path = _REPO_ROOT) -> None:
        self._path = repo_root / _STATE_DIR_NAME / _STATE_FILE_NAME

    def state_file(self) -> Path:
        return self._path

    def reset(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not delete UI state file %s: %s", self._path, exc)
