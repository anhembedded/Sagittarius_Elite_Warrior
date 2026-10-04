"""One mode of the workbench window, holding one of today's screens
(`EPIC-033C`).

The Engine's `WorkbenchShell` switches between `RegionHost`s. Today's screens
are views, not hosts: most draw a `PageShell`, and two (Bots, Dev Board) draw
a `WorkbenchSurface` of their own inside the view. `ModeHost` is the host the
shell needs, with the view as its central widget, until each mode is laid out
as a workbench of its own (`EPIC-033H`-`033L`, `033P`), when this class goes.

When the view draws on a surface (a `RegionHost` that is its direct child),
that surface is where the panels are, so the
View menu's panel and toolbar toggles and the mode's layout (save, restore,
Reset layout) are the surface's. A view without one has no panels: its View
entries are empty and its layout is the central widget alone.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget
from sagittarius_engine.extensions.pyside_mvc.runtime.region_host import RegionHost
from sagittarius_engine.extensions.pyside_mvc.runtime.region_kind import RegionKind
from sagittarius_engine.extensions.pyside_mvc.runtime.surface_declaration import (
    SurfaceDeclaration,
)

#: The one place a `ModeHost` accepts: its central widget.
_SCREEN_PLACE = "screen"
_SURFACE_PREFIX = "mode::"


def _surface_of(view: QWidget) -> RegionHost | None:
    """The workbench surface a view draws its panels on: a `RegionHost` that
    is the view's own direct child, as the Bots tab and the Dev Board build
    it. A host nested deeper belongs to a panel, not to the screen."""
    return view.findChild(RegionHost, options=Qt.FindChildOption.FindDirectChildrenOnly)


class ModeHost(RegionHost):
    """A mode's host: the screen's view in the centre, the view's own
    surface (when it has one) answering for panels and layout."""

    def __init__(self, mode_id: str, view: QWidget) -> None:
        super().__init__(
            SurfaceDeclaration(
                surface_id=f"{_SURFACE_PREFIX}{mode_id}",
                accepts=frozenset({_SCREEN_PLACE}),
            ),
            {_SCREEN_PLACE: RegionKind.CENTRAL},
        )
        self.setObjectName(f"workbench::mode::{mode_id}")
        self._view = view
        self._inner = _surface_of(view)
        self.place_widget(_SCREEN_PLACE, view)

    @property
    def view(self) -> QWidget:
        return self._view

    def dock_toggle_actions(self) -> tuple[QAction, ...]:
        if self._inner is not None:
            return self._inner.dock_toggle_actions()
        return super().dock_toggle_actions()

    def toolbar_toggle_actions(self) -> tuple[QAction, ...]:
        if self._inner is not None:
            return self._inner.toolbar_toggle_actions()
        return super().toolbar_toggle_actions()

    @property
    def layout_version(self) -> int:
        if self._inner is not None:
            return self._inner.layout_version
        return super().layout_version

    def capture_default_perspective(self) -> None:
        if self._inner is not None:
            self._inner.capture_default_perspective()
            return
        super().capture_default_perspective()

    def reset_perspective(self) -> bool:
        if self._inner is not None:
            return self._inner.reset_perspective()
        return super().reset_perspective()

    def save_perspective(self) -> bytes:
        if self._inner is not None:
            return self._inner.save_perspective()
        return super().save_perspective()

    def restore_perspective(self, blob: bytes) -> bool:
        if self._inner is not None:
            return self._inner.restore_perspective(blob)
        return super().restore_perspective(blob)
