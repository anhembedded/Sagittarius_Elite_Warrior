"""`EPIC-010` D1/B2 — the persistent store, backed by a second `ConfigManager`.

@par Why not a hand-written JSON store
The project already has exactly one persistence paradigm: `ConfigManager`,
`set()`, `save()`. Adding a second way to put a dict on disk would cost every
future reader a second thing to learn, for no behaviour the first one lacks.
Measured — `scripts/ui_state_store_feasibility_probe.py` — a second
`ConfigManager` instance already provides the two hardest parts for free:

  H2  `save()` writes only the keys `set()` since the last save, merged onto
      the file's current contents. That is per-slice merge, which is what makes
      lazily-constructed presenters safe.
  H3  `JsonSource.read()` swallows `JSONDecodeError` and yields `{}`, so a
      truncated file degrades to defaults instead of blocking boot.

@par Why not the same file as `user_config.json`
It is git-tracked and holds `API_KEY`/`API_SECRET`, and the Sanity tier loads
it with `writable=True`. More fundamentally, a *preference* is declared by the
user and must be honoured verbatim, while a remembered value is a side effect
of using the application and must be discardable in silence. Opposite failure
policies do not belong in one file.

@par The accepted cost
`ConfigManager.save()` opens the file with `open(path, "w")` — no temp file, no
rename. A crash mid-write truncates it, and the next launch falls back to
defaults everywhere. For hint-class data that is an acceptable loss, and it is
the same "hints may be lost" logic applied consistently. It is locked by
`test_truncated_file_yields_empty_document_without_raising` rather than left as
a comment, because `architecture-rule.md` §7.1 requires an accepted cost to
have a test.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.presentation.ui.state.ports.i_state_store import (
    IStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ports.i_state_store_locator import (
    IStateStoreLocator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import (
    StateData,
    StateScope,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

#: Under "App" so `StdLogger`'s handlers apply — a logger outside that tree has
#: no handler and drops everything at INFO, which was `BUG-009`'s second cause.
logger = logging.getLogger("App.UiState")

#: Bumped only when a stored shape stops being readable by this code. A file
#: declaring a *higher* number was written by a newer build and is ignored
#: wholesale rather than guessed at.
SCHEMA_VERSION = 1

#: Reserved top-level key. Not a slice, so `read()` must never hand it to a
#: contributor as if it were one.
_SCHEMA_VERSION_KEY = "schema_version"


class ConfigManagerStateStore(IStateStore):
    """Persistent slices, stored via the engine's own `ConfigManager`."""

    def __init__(self, locator: IStateStoreLocator) -> None:
        self._locator = locator
        self._degraded = False
        self._manager = ConfigManager()
        self._manager.load_json(str(locator.state_file()), writable=True)

    def read(self, scope: StateScope) -> StateData:
        """Returns `scope`'s slice, or an empty mapping."""
        if not self._schema_is_readable():
            return {}
        stored = self._manager.get(scope.storage_key, None)
        if not isinstance(stored, dict):
            # Absent, or written as something that is not a slice. Both mean
            # "no usable memory here" — see IStateStore.read's contract.
            return {}
        return stored

    def write(self, scope: StateScope, data: StateData) -> None:
        """Replaces `scope`'s slice; every other slice is left untouched."""
        self._manager.set(_SCHEMA_VERSION_KEY, SCHEMA_VERSION)
        self._manager.set(scope.storage_key, dict(data))
        self.flush()

    def discard(self, scope: StateScope) -> None:
        """Empties `scope`'s slice.

        @details Writes an empty slice rather than removing the key, because
        `ConfigManager.save()` merges and has no notion of deletion. An empty
        slice reads back as "no usable memory", which is the same observable
        result, and whole-file removal is `IStateStoreLocator.reset()`'s job.
        """
        self.write(scope, {})

    def discard_keys(self, scope: StateScope, keys: Iterable[str]) -> None:
        """Rewrites `scope`'s slice without `keys` (`EPIC-010H`)."""
        remaining = {
            key: value
            for key, value in self.read(scope).items()
            if key not in set(keys)
        }
        self.write(scope, remaining)

    def flush(self) -> None:
        """Writes pending slices out. Never raises."""
        try:
            self._manager.save()
        except (OSError, ValueError) as exc:
            self._enter_degraded(exc)

    def _schema_is_readable(self) -> bool:
        """Whether the stored document was written by this build or an older one."""
        stored_version = self._manager.get(_SCHEMA_VERSION_KEY, SCHEMA_VERSION)
        if not isinstance(stored_version, int):
            return False
        return stored_version <= SCHEMA_VERSION

    def _enter_degraded(self, exc: Exception) -> None:
        """Logs the first write failure and stays quiet about the rest.

        @details One line, not one per attempt: a read-only disk would
        otherwise produce a warning on every debounce tick for the rest of the
        session, and a log nobody can read is a log nobody reads.
        """
        if self._degraded:
            return
        self._degraded = True
        logger.warning(
            "UI state will not persist this session (%s: %s). "
            "The application is unaffected; remembered values simply reset.",
            type(exc).__name__,
            exc,
        )
