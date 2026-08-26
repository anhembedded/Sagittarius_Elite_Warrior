"""`EPIC-010` — the session store, and the test double.

@details One class serving two roles is not a shortcut here: a `SESSION` scope
is defined (design §4.2) to never reach disk, so its store *is* "hold this in a
dict until the process ends" — which is also exactly what a test needs from a
store it can inspect. There is no second thing to build.
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


class InMemoryStateStore(IStateStore):
    """Holds slices in a plain `dict`. Nothing here ever touches disk."""

    def __init__(self) -> None:
        self._slices: dict[str, StateData] = {}

    def read(self, scope: StateScope) -> StateData:
        return self._slices.get(scope.storage_key, {})

    def write(self, scope: StateScope, data: StateData) -> None:
        self._slices[scope.storage_key] = dict(data)

    def discard(self, scope: StateScope) -> None:
        self._slices.pop(scope.storage_key, None)

    def discard_keys(self, scope: StateScope, keys: Iterable[str]) -> None:
        slice_data = self._slices.get(scope.storage_key)
        if slice_data is None:
            return
        # Rebuilt rather than mutated in place: the values are typed
        # `StateData`, a read-only `Mapping`, and a caller that kept the
        # mapping it wrote would otherwise see it change underneath.
        dropped = set(keys)
        self._slices[scope.storage_key] = {
            key: value for key, value in slice_data.items() if key not in dropped
        }

    def flush(self) -> None:
        """No-op — nothing is ever pending; every write already lands."""
        return
