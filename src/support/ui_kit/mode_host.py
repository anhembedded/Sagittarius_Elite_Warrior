"""One mode of the workbench window, holding one of today's screens
(`EPIC-033C`).

The Engine's `WorkbenchShell` switches between `RegionHost`s. Today's screens
are views, not hosts: Bots draws a
`WorkbenchSurface` of its own inside the view (the Dev Board did too, until
`EPIC-033P` deleted it). `ModeHost` is the host the
shell needs, with the view as its central widget, until each mode is laid out
as a workbench of its own (`EPIC-033H`-`033L`, `033P`), when this class goes.

When the view draws on a surface (a `RegionHost` that is its direct child),
that surface is where the panels are, so the View menu's panel toggles are the
surface's. A view without one has no panels: its View entries are empty and
its layout is the central widget alone.

Every mode also has a commands toolbar (`EPIC-033D`): the window places each
contributed command marked for the toolbar there, as the action its menu entry
shares. View → Toolbars lists it beside the surface's own toolbars.

A mode's central widget is a frame holding its message bars above the screen
(`BOT-169`); `view` is the screen itself.

The mode's layout is both: this host's own (the commands toolbar) and the
surface's (the panels). Window → Reset layout resets both, and the window
remembers both across a restart, one saved layout per host
(`remembered_hosts`).

A view that holds several surfaces and shows one at a time (`ISurfaceStack`:
the Trade mode, a surface per venue, `EPIC-033I`) answers for itself: View
lists the panels of the surface that shows, every surface's layout is
remembered under its own id, and Reset layout resets the one that shows.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.message_bar import MessageBarHost
from Sagittarius_Elite_Warrior.src.support.ui_kit.surface_stack import ISurfaceStack
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
    is the view's own direct child, as the Bots tab builds it. A host nested deeper belongs to a panel, not to the screen."""
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
        self._stack = view if isinstance(view, ISurfaceStack) else None
        self._inner = _surface_of(view)
        # `BOT-169` — the mode's message bars sit above its screen, taking no
        # height until a background failure is told (`INotifier`).
        self._message_bars = MessageBarHost()
        frame = QWidget()
        column = QVBoxLayout(frame)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._message_bars)
        column.addWidget(view, 1)
        self._frame = frame
        self.place_widget(_SCREEN_PLACE, frame)

    @property
    def view(self) -> QWidget:
        return self._view

    @property
    def message_bars(self) -> MessageBarHost:
        """Where this mode's background failures are shown."""
        return self._message_bars

    def dock_toggle_actions(self) -> tuple[QAction, ...]:
        shown = self._shown_surface()
        if shown is not None:
            return shown.dock_toggle_actions()
        return super().dock_toggle_actions()

    def add_command(self, action: QAction) -> None:
        """Puts a command on this mode's toolbar, whose buttons write their
        text beside their icon: an icon alone says nothing of what a button
        does, and a text alone reads as a label, not a button (`BOT-164`;
        Qt `QToolBar.setToolButtonStyle`)."""
        self.place_action(_COMMANDS_PLACE, action)
        for bar in self.findChildren(
            QToolBar, options=Qt.FindChildOption.FindDirectChildrenOnly
        ):
            bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            # An icon one line of text high: the style's own icon size is
            # taller than a line and made the toolbar, and with it every
            # mode's minimum height, grow by 9 px.
            line = bar.fontMetrics().height()
            bar.setIconSize(QSize(line, line))

    def toolbar_toggle_actions(self) -> tuple[QAction, ...]:
        own = super().toolbar_toggle_actions()
        shown = self._shown_surface()
        if shown is not None:
            return (*shown.toolbar_toggle_actions(), *own)
        return own

    def remembered_hosts(self) -> tuple[RegionHost, ...]:
        """The hosts whose layouts are saved on exit and restored on start
        (`ui-presentation-rule.md` §8): this one, for the commands toolbar,
        then the view's surfaces, for the panels. This host comes first: when
        its saved layout no longer applies, its reset also resets the
        surfaces, and their own saved layouts, restored after it, win.
        """
        return (self, *self._surfaces())

    def capture_default_perspective(self) -> None:
        # The commands toolbar is this host's own, outside the view's
        # surfaces: its default is captured, and reset, here as well.
        super().capture_default_perspective()
        for surface in self._surfaces():
            surface.capture_default_perspective()

    def reset_perspective(self) -> bool:
        """Window → Reset layout: the commands toolbar and the shown
        surface's panels go back to the default (`EPIC-033C`). A surface
        not showing keeps its own layout, as each venue of the Trade mode
        keeps its own (`ISurfaceStack`); nothing resets it later: the person
        resets it while it shows. Qt also
        lays out a hidden window's restored state only once it shows, and
        leaves the tab bars of the state it replaced drawn over the panels
        (measured 2026-10-06, `EPIC-033I`)."""
        own = super().reset_perspective()
        shown = self._shown_surface()
        if shown is not None:
            return shown.reset_perspective() and own
        return own

    def _surfaces(self) -> tuple[RegionHost, ...]:
        if self._stack is not None:
            return tuple(self._stack.surfaces())
        return (self._inner,) if self._inner is not None else ()

    def _shown_surface(self) -> RegionHost | None:
        if self._stack is not None:
            return self._stack.shown_surface()
        return self._inner
