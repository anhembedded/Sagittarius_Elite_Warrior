"""A surface, rendered as the `QMainWindow` workbench HLD §11.2 specifies.

`IPlaceHost` has existed since PR 0.2 with **no implementation**: the places
were declared, the descriptor was validated, and nothing could actually show a
contributed widget. This is that implementation, and it is the first half of
PR 1.4 — the mechanism, before either screen moves onto it.

@par Every place maps onto a part `QMainWindow` already has
"Apply before you invent" (`onb` §12.5): MetaTrader and TWS are workbenches of
dockable panels around a central chart; Qt Creator has modes with a saved
perspective each. Nothing here is a hand-drawn substitute for a standard part,
which is the Familiarity principle stated as code (ADR D20–D22):

| `Place` | Rendered as |
| :--- | :--- |
| `HEADER` | the top `QToolBar` |
| `CONTEXT_BAR` | a second `QToolBar`, on its own row under the first |
| `WORKSPACE` | the central widget — exactly one, a second is a programming error |
| `RAIL` | a `QDockWidget` in the right dock area |
| `CONSOLE` | a `QDockWidget` in the bottom dock area |
| `DEV_PROBE` | a `QDockWidget` in the right dock area, tabbed with the rail |
| `STATUS_TILE` | a permanent widget in the `QStatusBar` |
| `MODAL` | **not placed** — kept as a dialog this surface can raise |

@par Why `MODAL` is stored rather than placed
A dialog is not part of a layout: it is how the user *does* something that needs
input and confirmation (HLD §11.3). So `place_widget(MODAL, ...)` wraps the
contributed body in a `QDialog` with the descriptor's title and keeps it; the
surface raises it when an action asks. Putting it in the layout instead would
mean a form permanently occupying space for something the user does
occasionally, which is the "card" shape this epic retired.

@par The perspective belongs to the user, not to the order field
`order` decides the initial dock order and nothing after that: once a user has
moved, tabbed, floated or hidden a panel, `save_perspective()` records it and
`restore_perspective()` puts it back. A blob that does not apply is **reported,
not raised** — the Robustness principle's own words are "saved perspectives are
keyed by app version and migrate or reset, never crash", so a stale or corrupt
perspective leaves the default layout standing and says so in the log.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QMainWindow,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ContributionError
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface

logger = logging.getLogger("App.UiKit.WorkbenchSurface")

#: Bumped when a change to this class's own layout would make an older saved
#: blob apply wrongly rather than fail (a renamed dock, a removed toolbar).
#: `QMainWindow.restoreState` compares it and refuses a mismatch, which is what
#: turns "migrate or reset" into something the toolkit does for us.
PERSPECTIVE_VERSION = 1

_DOCK_AREA = {
    Place.RAIL: Qt.DockWidgetArea.RightDockWidgetArea,
    Place.CONSOLE: Qt.DockWidgetArea.BottomDockWidgetArea,
    Place.DEV_PROBE: Qt.DockWidgetArea.RightDockWidgetArea,
}


class WorkbenchSurface(QMainWindow):
    """One surface: a nested `QMainWindow` that renders contributed widgets.

    Satisfies `IPlaceHost` **structurally**, with no base class: that port is a
    `Protocol` for exactly this reason (`architecture-rule.md` §2.1 reason (a) —
    `ABCMeta` conflicts with Shiboken's metaclass, so inheriting it raises
    `TypeError` on import). `test_workbench_surface.py` asserts the
    `isinstance` holds, and `mypy` checks the shape because `support/` is
    inside its gate (only `src/presentation/` is excluded).
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
        super().__init__(parent)
        self._surface = surface
        self._banner: QToolBar | None = None
        self._header: QToolBar | None = None
        self._context_bar: QToolBar | None = None
        self._docks: dict[str, QDockWidget] = {}
        self._modals: dict[str, QDialog] = {}
        # A parent is not enough: `QMainWindow` sets the `Window` flag on
        # itself, so nested in a page or the shell's stacked widget it would draw
        # its own title bar and frame. `Qt.WindowType.Widget` is `0`, so this
        # call *clears* the flag set — which is the documented way to un-window
        # a `QMainWindow`, and measured: without it `isWindow()` stays true
        # even with a parent.
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setObjectName(f"surface::{surface.surface_id}")
        self._add_environment_banner()

    # -- IPlaceHost (structural, no base class) ----------------------------

    @property
    def surface_id(self) -> str:
        return self._surface.surface_id

    def accepts(self) -> frozenset[Place]:
        return self._surface.accepts

    def place_widget(
        self, place: Place, widget: QWidget, *, title: str | None = None
    ) -> None:
        if place not in self._surface.accepts:
            raise ContributionError(
                f"surface {self.surface_id!r} cannot render {place.value}; "
                f"it accepts {sorted(p.value for p in self._surface.accepts)}."
            )
        if place is Place.HEADER:
            self._toolbar_header().addWidget(widget)
        elif place is Place.CONTEXT_BAR:
            self._toolbar_context().addWidget(widget)
        elif place is Place.WORKSPACE:
            self._set_workspace(widget)
        elif place in _DOCK_AREA:
            self._add_dock(place, widget, title)
        elif place is Place.STATUS_TILE:
            self.statusBar().addPermanentWidget(widget)
        elif place is Place.MODAL:
            self._keep_modal(widget, title)
        else:
            raise ContributionError(
                f"surface {self.surface_id!r} accepts {place.value} but this "
                "host does not know how to render it — a Place was added "
                "without teaching the workbench about it."
            )

    # -- the perspective ---------------------------------------------------

    def save_perspective(self) -> bytes:
        """This user's dock layout, for `restore_perspective()` to put back."""
        # Two steps, and mypy earned both: `saveState` answers a `QByteArray`,
        # whose stubs declare no `bytes()` overload, and whose `.data()` is
        # typed `bytes | bytearray | memoryview`. `bytes(...)` around *that*
        # narrows it, and only the gate's type check would have noticed either.
        return bytes(self.saveState(PERSPECTIVE_VERSION).data())

    def restore_perspective(self, blob: bytes) -> bool:
        """Applies a saved layout. `False` (and a log line) when it does not
        apply, leaving the default layout standing — never an exception."""
        if not blob:
            return False
        if self.restoreState(blob, PERSPECTIVE_VERSION):
            return True
        logger.info(
            "Surface %r kept its default layout: the saved perspective does "
            "not apply (version %d, %d bytes).",
            self.surface_id,
            PERSPECTIVE_VERSION,
            len(blob),
        )
        return False

    # -- modals ------------------------------------------------------------

    def modal_titles(self) -> tuple[str, ...]:
        """Which dialogs this surface can raise, sorted, so a caller can build
        the actions that raise them without knowing who contributed what."""
        return tuple(sorted(self._modals))

    def show_modal(self, title: str) -> QDialog:
        """Raises the dialog contributed under `title`.

        Returns it rather than its result code: the caller decides `exec()`
        (modal) or `show()` (modeless), and a test wants the widget.
        """
        dialog = self._modals.get(title)
        if dialog is None:
            raise ContributionError(
                f"surface {self.surface_id!r} has no dialog titled {title!r}; "
                f"it has {list(self.modal_titles())}."
            )
        return dialog

    # -- the parts ---------------------------------------------------------

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

    def _toolbar_header(self) -> QToolBar:
        if self._header is None:
            self._header = QToolBar("Header", self)
            self._header.setObjectName(f"{self.objectName()}::header")
            self._header.setMovable(False)
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._header)
        return self._header

    def _toolbar_context(self) -> QToolBar:
        if self._context_bar is None:
            # Its own row under the header: the context bar says what the
            # surface is pointed at, and reading it next to the mode's own
            # controls is what HLD §11.2 separates them for.
            self._toolbar_header()
            self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
            self._context_bar = QToolBar("Context", self)
            self._context_bar.setObjectName(f"{self.objectName()}::context_bar")
            self._context_bar.setMovable(False)
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._context_bar)
        return self._context_bar

    def _set_workspace(self, widget: QWidget) -> None:
        if self.centralWidget() is not None:
            raise ContributionError(
                f"surface {self.surface_id!r} already has a workspace. A "
                "surface has one subject; a second contribution to WORKSPACE "
                "is two modules each believing they own the centre."
            )
        self.setCentralWidget(widget)

    def _add_dock(self, place: Place, widget: QWidget, title: str | None) -> None:
        if not title:
            raise ContributionError(
                f"a {place.value} contributed to {self.surface_id!r} has no "
                "title. A dock the user can move, tab and close needs a name "
                "on it to find it again (HLD §11.3)."
            )
        if title in self._docks:
            raise ContributionError(
                f"surface {self.surface_id!r} already has a panel titled "
                f"{title!r}. Two docks with one title are indistinguishable in "
                "the View menu and in a saved perspective."
            )
        dock = QDockWidget(title, self)
        # The object name is what `saveState()` keys a dock by — without it the
        # perspective silently fails to restore that panel.
        dock.setObjectName(f"{self.objectName()}::{place.value}::{title}")
        dock.setWidget(widget)
        self.addDockWidget(_DOCK_AREA[place], dock)
        previous = self._last_dock_in(_DOCK_AREA[place])
        if previous is not None:
            # Tab rather than stack: three panels stacked in one dock area
            # leave none of them readable, and the user can pull one out.
            self.tabifyDockWidget(previous, dock)
        self._docks[title] = dock

    def _last_dock_in(self, area: Qt.DockWidgetArea) -> QDockWidget | None:
        existing = [
            dock
            for dock in self._docks.values()
            if self.dockWidgetArea(dock) == area and dock is not None
        ]
        return existing[-1] if existing else None

    def _keep_modal(self, widget: QWidget, title: str | None) -> None:
        if not title:
            raise ContributionError(
                f"a modal contributed to {self.surface_id!r} has no title. "
                "Every dialog's title names the action it performs (HLD §11.3)."
            )
        if title in self._modals:
            raise ContributionError(
                f"surface {self.surface_id!r} already has a dialog titled {title!r}."
            )
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        self._modals[title] = dialog
