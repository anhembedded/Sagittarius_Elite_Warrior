"""One mode of the workbench window, holding one of today's screens
(`EPIC-033C`).

The Engine's `WorkbenchShell` switches between `RegionHost`s. Today's screens
are views, not hosts: most draw a `PageShell`, and two (Bots, Dev Board) draw
a `WorkbenchSurface` of their own inside the view. `ModeHost` is the host the
shell needs, with the view as its central widget, until each mode is laid out
as a workbench of its own (`EPIC-033H`-`033L`, `033P`), when this class goes.

When the view draws on a surface (a `RegionHost` that is its direct child),
that surface is where the panels are, so the View menu's panel toggles are the
surface's. A view without one has no panels: its View entries are empty and
its layout is the central widget alone.

Every mode also has a commands toolbar (`EPIC-033D`): the window places each
contributed command marked for the toolbar there, as the action its menu entry
shares. View → Toolbars lists it beside the surface's own toolbars.

The mode's layout is both: this host's own (the commands toolbar) and the
surface's (the panels). Window → Reset layout resets both, and the window
remembers both across a restart, one saved layout per host
(`remembered_hosts`).
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

#: The places a `ModeHost` accepts: its central widget, and the toolbar its
#: mode's commands go on.
_SCREEN_PLACE = "screen"
_COMMANDS_PLACE = "commands"
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
                accepts=frozenset({_SCREEN_PLACE, _COMMANDS_PLACE}),
            ),
            {
                _SCREEN_PLACE: RegionKind.CENTRAL,
                _COMMANDS_PLACE: RegionKind.TOP_TOOLBAR,
            },
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

    def add_command(self, action: QAction) -> None:
        """Puts a command on this mode's toolbar."""
        self.place_action(_COMMANDS_PLACE, action)

    def toolbar_toggle_actions(self) -> tuple[QAction, ...]:
        own = super().toolbar_toggle_actions()
        if self._inner is not None:
            return (*self._inner.toolbar_toggle_actions(), *own)
        return own

    def remembered_hosts(self) -> tuple[RegionHost, ...]:
        """The hosts whose layouts are saved on exit and restored on start
        (`ui-presentation-rule.md` §8): this one, for the commands toolbar,
        then the view's surface, for the panels. This host comes first: when
        its saved layout no longer applies, its reset also resets the
        surface, and the surface's own saved layout, restored after it, wins.
        """
        if self._inner is not None:
            return (self, self._inner)
        return (self,)

    def capture_default_perspective(self) -> None:
        # The commands toolbar is this host's own, outside the view's
        # surface: its default is captured, and reset, here as well.
        super().capture_default_perspective()
        if self._inner is not None:
            self._inner.capture_default_perspective()

    def reset_perspective(self) -> bool:
        """Window → Reset layout: the commands toolbar and the surface's
        panels both go back to the default (`EPIC-033C`)."""
        own = super().reset_perspective()
        if self._inner is not None:
            return self._inner.reset_perspective() and own
        return own
