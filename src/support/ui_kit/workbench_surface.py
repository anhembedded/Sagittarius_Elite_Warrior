"""A surface, rendered as the `QMainWindow` workbench HLD §11.2 specifies.

`IPlaceHost` has existed since PR 0.2 with **no implementation**: the places
were declared, the descriptor was validated, and nothing could actually show a
contributed widget. `WorkbenchSurface` is that implementation (PR 1.4a).

**The rendering half is rebuilt on the Engine's `RegionHost` (`EPIC-025F` PR 5.4,
`TASK-043` E2).** Dock management, central widget placement, toolbars, modal
dialog storage, and perspective save/restore (`saveState`/`restoreState`) are
now inherited directly from `sagittarius_engine.extensions.pyside_mvc.runtime.RegionHost`,
retiring the application's hand-rolled copy of the same window management code.

What stays here, and could not move:
1. **The application's closed vocabulary (`Place`)**: mapped to the Engine's
   anatomy (`RegionKind`) via `_PLACE_TO_REGION` at construction.
2. **The environment banner**: `_environment_banner_factory` and `_add_environment_banner()`,
   which provides the "which venue am I in" warning row (`EPIC-021K`) above the header.
3. **Backwards-compatible toolbar object names**: `::header` and `::context_bar`,
   preserving query compatibility for existing view coordinators and tests.
4. **App-specific error translation**: translating `EngineContributionError` to the
   application's own `ContributionError`.

| `Place` | `RegionKind` | Rendered as |
| :--- | :--- | :--- |
| `HEADER` | `TOP_TOOLBAR` | the top `QToolBar` |
| `CONTEXT_BAR` | `SECONDARY_TOOLBAR` | a second `QToolBar`, on its own row under the first |
| `WORKSPACE` | `CENTRAL` | the central widget — exactly one |
| `RAIL` | `DOCK_RIGHT` | a `QDockWidget` in the right dock area |
| `CONSOLE` | `DOCK_BOTTOM` | a `QDockWidget` in the bottom dock area |
| `DEV_PROBE` | `DOCK_RIGHT` | a `QDockWidget` in the right dock area, tabbed with the rail |
| `STATUS_TILE` | `STATUS_BAR` | a permanent widget in the `QStatusBar` |
| `MODAL` | `MODAL` | **not placed** — kept as a dialog this surface can raise |
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QToolBar,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ContributionError
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from sagittarius_engine.extensions.pyside_mvc.runtime.contribution_error import (
    ContributionError as EngineContributionError,
)
from sagittarius_engine.extensions.pyside_mvc.runtime.region_host import (
    PERSPECTIVE_VERSION,
    RegionHost,
)
from sagittarius_engine.extensions.pyside_mvc.runtime.region_kind import RegionKind
from sagittarius_engine.extensions.pyside_mvc.runtime.surface_declaration import (
    SurfaceDeclaration,
)

logger = logging.getLogger("App.UiKit.WorkbenchSurface")

__all__ = ["PERSPECTIVE_VERSION", "WorkbenchSurface"]

#: Mapping from this application's closed `Place` vocabulary to the Engine's
#: closed `RegionKind` window anatomy.
_PLACE_TO_REGION: dict[Place, RegionKind] = {
    Place.HEADER: RegionKind.TOP_TOOLBAR,
    Place.CONTEXT_BAR: RegionKind.SECONDARY_TOOLBAR,
    Place.WORKSPACE: RegionKind.CENTRAL,
    Place.RAIL: RegionKind.DOCK_RIGHT,
    Place.CONSOLE: RegionKind.DOCK_BOTTOM,
    Place.DEV_PROBE: RegionKind.DOCK_RIGHT,
    Place.STATUS_TILE: RegionKind.STATUS_BAR,
    Place.MODAL: RegionKind.MODAL,
}


class WorkbenchSurface(RegionHost):
    """One surface: a nested `QMainWindow` that renders contributed widgets.

    Inherits from `RegionHost` (`sagittarius_engine.extensions.pyside_mvc.runtime.RegionHost`)
    and satisfies `IPlaceHost` and `IRegionHost` **structurally**.
    """

    #: The global "which venue am I in" banner, set once by the composition
    #: root and never here: this package knows no domain concept, so it holds
    #: a bare widget factory and never `VenueAlignment` itself. `PageShell`
    #: carries the identical mechanism for the screens not yet converted, and
    #: `test_environment_banner_all_screens.py` scans every navigable route
    #: for the widget — a screen that moves from one shell to the other must
    #: keep showing it, which is why the host has the slot at all rather than
    #: each converted View remembering to add a banner itself.
    #:
    #: A `QWidget` cannot be shared across parents, so each surface calls the
    #: factory for its own instance; `None` (the default) means no banner,
    #: which is every construction in this package's own tests.
    _environment_banner_factory: Callable[[], QWidget] | None = None

    @classmethod
    def set_environment_banner_factory(
        cls, factory: Callable[[], QWidget] | None
    ) -> None:
        """Registers (or clears, with `None`) the factory every surface built
        from now on uses for its banner row."""
        cls._environment_banner_factory = factory

    def __init__(self, surface: Surface, parent: QWidget | None = None) -> None:
        self._app_surface = surface
        for place in surface.accepts:
            if place not in _PLACE_TO_REGION:
                raise ContributionError(
                    f"surface {surface.surface_id!r} accepts {place.value} but this "
                    "host does not know how to render it — a Place was added "
                    "without teaching the workbench about it."
                )

        surface_decl = SurfaceDeclaration(
            surface_id=surface.surface_id,
            accepts=frozenset(place.value for place in surface.accepts),
        )
        place_regions = {
            place.value: _PLACE_TO_REGION[place] for place in surface.accepts
        }
        super().__init__(
            surface=surface_decl,
            place_regions=place_regions,
            parent=parent,
        )
        self._banner: QToolBar | None = None
        self._add_environment_banner()

    # -- IPlaceHost (structural, no base class) ----------------------------

    @property
    def surface_id(self) -> str:
        return self._app_surface.surface_id

    def accepts(self) -> frozenset[Place]:
        return self._app_surface.accepts

    def place_widget(
        self, place: Place | str, widget: QWidget, *, title: str | None = None
    ) -> None:
        place_obj = place if isinstance(place, Place) else Place(place)
        if place_obj not in self._app_surface.accepts:
            raise ContributionError(
                f"surface {self.surface_id!r} cannot render {place_obj.value}; "
                f"it accepts {sorted(p.value for p in self._app_surface.accepts)}."
            )
        try:
            super().place_widget(place_obj.value, widget, title=title)
        except EngineContributionError as exc:
            raise ContributionError(str(exc)) from exc

    def show_modal(self, title: str) -> QDialog:
        try:
            return super().show_modal(title)
        except EngineContributionError as exc:
            raise ContributionError(str(exc)) from exc

    # -- Toolbars with application naming ----------------------------------

    def _toolbar_top(self) -> QToolBar:
        toolbar = super()._toolbar_top()
        toolbar.setObjectName(f"{self.objectName()}::header")
        return toolbar

    def _toolbar_secondary(self) -> QToolBar:
        toolbar = super()._toolbar_secondary()
        toolbar.setObjectName(f"{self.objectName()}::context_bar")
        return toolbar

    def _set_central(self, widget: QWidget) -> None:
        if self.centralWidget() is not None:
            raise ContributionError(
                f"surface {self.surface_id!r} already has a workspace. A "
                "surface has one subject; a second contribution to WORKSPACE "
                "is two modules each believing they own the centre."
            )
        self.setCentralWidget(widget)

    # -- Environment banner ------------------------------------------------

    def _add_environment_banner(self) -> None:
        """The banner row, built first so it sits above the header.

        A `QToolBar` rather than a widget above the window: a nested
        `QMainWindow` has no layout of its own to put one in, and the top
        toolbar area is the part of a `QMainWindow` that spans the full width
        above everything else. Not movable and not floatable — a warning the
        user can drag into a corner is a warning that stops working.
        """
        factory = type(self)._environment_banner_factory
        if factory is None:
            return
        self._banner = QToolBar("Environment", self)
        self._banner.setObjectName(f"{self.objectName()}::environment")
        self._banner.setMovable(False)
        self._banner.setFloatable(False)
        self._banner.addWidget(factory())
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._banner)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
