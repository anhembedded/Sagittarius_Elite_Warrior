"""`QmlOverlay` — a modal whose *body* is QML, inside the widget chrome.

@par Why the body only, and not the whole dialog
`EPIC-015` §1: QML nests inside QtWidgets and Qt does not support the
reverse. Keeping `Overlay`'s chrome (title, subtitle, footer buttons,
modality, sizing) means a migrated modal sits beside the nine that are not
migrated yet and looks like them, and it means the chrome's existing tests
keep covering it. Only the part being migrated changes.

@par The body is a `QuickSurface`, not a hand-built `QQuickWidget`
`BUG-115`: this class used to build its own `QQuickWidget` with a
transparent clear colour "so `Overlay`'s SURFACE background shows behind
the QML body" — which is only what happens on the software rendering path
(`offscreen`, `widget.grab()`); on every real desktop session the body
rendered black (X11) or see-through (Wayland), and nine more hosts copied
the same lines. `qml/embed/QuickSurface` now owns the whole embedding
contract, including the rule that made this class wrong: the scene is
opaque and clears to the token of the `StyleRole` it sits on — here
`Overlay`'s own `SURFACE`.

@par A cost this host does NOT solve
Tearing a QML scene down writes `TypeError: Cannot read property ... of null`
to stderr as bindings re-evaluate against a half-destroyed context. A
`closeEvent` clearing the source was tried and **measured to change nothing**
(16 lines either way across the pilot's tests), because the dialogs are
collected rather than closed, so it was removed rather than shipped as a
comment that lies. This is the benign-but-loud noise `CLAUDE.md` rule 2 was
written for, and the reason that rule insists on `> logfile 2>&1` then
grepping, never `| tail`. Reading a truncated console here shows a wall of
red under a passing run.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Overlay, StyleRole

#: The inner widget's `objectName` — what `QTest` clicks and tests address.
_BODY_OBJECT_NAME = "qmlBody"


class QmlOverlay(Overlay):
    """
    @brief An `Overlay` whose body is a `.qml` file bound to a widget ViewModel.

    @param qml_file Absolute path to the `.qml` to load.
    @param context Objects exposed to QML as context properties. The widget's
        own ViewModel goes here under `vm`; `Theme` is added automatically.
    @raise RuntimeError If the `.qml` fails to load — loud, once, instead of
        an empty rectangle (`qml-rule.md` §7). `QuickSurface` raises it.
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        *,
        qml_file: Path,
        context: dict[str, QObject],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, subtitle, parent=parent)
        self._surface = QuickSurface(
            qml_file,
            surface=StyleRole.SURFACE,
            context=context,
            object_name=_BODY_OBJECT_NAME,
        )
        self.body_layout.addWidget(self._surface, 1)

    @property
    def root_object(self) -> QObject:
        """The loaded QML root, for tests to `qml_item`/`findChild` into by `objectName`."""
        return self._surface.root_object

    @property
    def quick_widget(self) -> QQuickWidget:
        """The body's inner `QQuickWidget` — the `QTest` target for clicks
        whose coordinates come from `item.mapToScene()`."""
        return self._surface.quick_widget
