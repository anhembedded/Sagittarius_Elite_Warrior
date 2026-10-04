"""Each mode's layout, remembered across runs (`EPIC-033C`).

The Engine's `PerspectiveStore` captures and restores every registered host,
keyed by surface id and layout version (a mismatched version restores the
mode's default and says so). It is a state contributor of the Engine's own
`ui_state`; this application remembers through its own `UiStateCoordinator`,
whose `StateScope` is a separate type. This adapter is the one place the two
meet: the Engine's store, under the application's scope.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import (
    StateData,
    StateScope,
)
from sagittarius_engine.extensions.pyside_mvc.runtime.region_host import RegionHost
from sagittarius_engine.extensions.pyside_mvc.workbench.perspective_store import (
    PERSPECTIVE_SCOPE_KEY,
    PerspectiveStore,
)


class ModePerspectives:
    """An `IStateContributor` (structural) for every mode's layout."""

    def __init__(self) -> None:
        self._store = PerspectiveStore()

    def register(self, host: RegionHost) -> None:
        self._store.register(host)

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key=PERSPECTIVE_SCOPE_KEY)

    def capture_state(self) -> StateData:
        return self._store.capture_state()

    def restore_state(self, data: StateData) -> None:
        self._store.restore_state(data)
