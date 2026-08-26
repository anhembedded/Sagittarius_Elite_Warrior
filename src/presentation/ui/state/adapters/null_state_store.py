"""`EPIC-010` — the store that remembers nothing, on purpose.

@details Two distinct reasons to need this, both real:

  - `BasePresenter`'s dependency on a state store is optional
    (`architecture-rule.md`'s "framework provides mechanism" boundary): an app
    or test that never registers `UiStateExtension` must still construct
    presenters. `container.resolve()` raises `DependencyResolutionError` on an
    unregistered type, so the fallback has to be a real object, not `None`.
  - The Sanity tier boots the real composition root and must not write to the
    developer's disk. `tests/sanity/conftest.py` already loads the real
    `user_config.json`; this store is what keeps a UI-state extension from
    making that worse.
"""

from __future__ import annotations

from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.presentation.ui.state.ports.i_state_store import (
    IStateStore,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import (
    StateData,
    StateScope,
)


class NullStateStore(IStateStore):
    """`read()` is always empty; every write is a no-op."""

    def read(self, scope: StateScope) -> StateData:
        return {}

    def write(self, scope: StateScope, data: StateData) -> None:
        return

    def discard(self, scope: StateScope) -> None:
        return

    def discard_keys(self, scope: StateScope, keys: Iterable[str]) -> None:
        """No-op — nothing was remembered to forget."""

    def flush(self) -> None:
        return
