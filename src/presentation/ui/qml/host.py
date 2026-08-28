"""`QmlOverlay` — a modal whose *body* is QML, inside the widget chrome.

@par Why the body only, and not the whole dialog
`EPIC-015` §1: QML nests inside QtWidgets and Qt does not support the
reverse. Keeping `Overlay`'s chrome (title, subtitle, footer buttons,
modality, sizing) means a migrated modal sits beside the nine that are not
migrated yet and looks like them, and it means the chrome's existing tests
keep covering it. Only the part being migrated changes.

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

@par Loud failure instead of a blank rectangle
A QML error is a *render-time* error — `EPIC-015`'s assessment names that as
one of the four standing costs of QML, and it is the one nothing else in
this repo's gate can see (`mypy` and `ruff` do not read `.qml`). A
`QQuickWidget` whose source failed to load renders an empty rectangle and
says nothing. This host raises instead, once, so every migrated modal
inherits the failure mode rather than each one discovering it.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

from ..kit import Overlay

#: The `Theme` context property every `.qml` in this package reads its
#: colours from. Set here rather than per file so no `.qml` ever needs a
#: colour literal — see `EPIC-015` §3.3 and `test_qml_has_no_colour_literals`.
_THEME_CONTEXT_NAME = "Theme"


def _ensure_customizable_style() -> None:
    """Pins Qt Quick Controls to a style that honours `background:` overrides.

    @details The platform default on Windows is the native style, which
    **silently ignores** `background:`/`contentItem:` and renders native
    chrome instead, logging only a warning. Called before any QML loads —
    including from tests, which never run the app bootstrapper, so a test
    cannot pass against chrome the user would never see.
    """
    from PySide6.QtQuickControls2 import QQuickStyle

    if QQuickStyle.name() != "Basic":
        QQuickStyle.setStyle("Basic")


class QmlOverlay(Overlay):
    """
    @brief An `Overlay` whose body is a `.qml` file bound to a widget ViewModel.

    @param qml_file Absolute path to the `.qml` to load.
    @param context Objects exposed to QML as context properties. The widget's
        own ViewModel goes here under `vm`; `Theme` is added automatically.
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
        _ensure_customizable_style()

        self._quick = QQuickWidget()
        self._quick.setObjectName("qmlBody")
        self._quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        # Transparent so `Overlay`'s own SURFACE styling shows behind the QML
        # body — without this the QQuickWidget paints its own opaque white
        # over the dialog's card background.
        self._quick.setClearColor(Qt.GlobalColor.transparent)

        # Held, not just passed through: a QML context property is a borrowed
        # pointer, and Python must keep the object alive for as long as the
        # scene can read it. Relying on every caller to store its own
        # ViewModel would make a dangling context property a caller bug that
        # only shows up as `TypeError: ... of null` on some other machine.
        self._context = dict(context)

        root_context = self._quick.rootContext()
        root_context.setContextProperty(_THEME_CONTEXT_NAME, get_theme_bridge())
        for name, obj in self._context.items():
            root_context.setContextProperty(name, obj)

        self._quick.setSource(QUrl.fromLocalFile(str(qml_file)))
        if self._quick.status() is not QQuickWidget.Status.Ready:
            raise RuntimeError(
                f"QML failed to load: {qml_file}\n"
                + "\n".join(error.toString() for error in self._quick.errors())
            )
        self.body_layout.addWidget(self._quick, 1)

    @property
    def root_object(self) -> QObject:
        """The loaded QML root, for tests to `findChild` into by `objectName`."""
        root = self._quick.rootObject()
        if root is None:  # pragma: no cover - __init__ raises before this
            raise RuntimeError("QML root object is missing")
        return root
