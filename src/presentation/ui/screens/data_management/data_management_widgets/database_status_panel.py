"""Embeds `DatabaseStatusTable.qml` inline in the Data Management screen's
own layout.

`EPIC-015` Phase 2: the first `QQuickWidget` in this app hosted directly on
a `kit.Panel` rather than through `QmlOverlay` (`qml/host.py`). This table
lives inside the screen's own layout — it is not a dialog — and
`QmlOverlay` wraps `Overlay` chrome (title bar, footer buttons, modality)
that an embedded table has no use for (`qml-rule.md` §0's pattern table:
neither "Modal QML" row applies here). `Panel` gives the same SURFACE
background/border the old `QFrame` + `apply_role(..., StyleRole.SURFACE)`
table card used, with no header row of its own — `DatabaseStatusTable.qml`
already renders its own header via `kit/PanelHeader`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Panel
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.DatabaseStatusTable.database_status_vm import (
    DatabaseStatusVM,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.style import ensure_qml_style
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.database_status_table_model import (
        DatabaseStatusTableModel,
    )

_QML = (
    Path(__file__).resolve().parents[3]
    / "qml"
    / "DatabaseStatusTable"
    / "DatabaseStatusTable.qml"
)


class DatabaseStatusPanel(Panel):
    """The Database Status table, embedded (not modal). Constructs
    `DatabaseStatusVM` around the screen's real `DatabaseStatusTableModel`
    (`DataManagementViewModel.status_model`) and re-emits its
    `rowActionRequested` so `DataManagementView` can connect the four real
    `requestInspectKlines`/`requestInspectGaps`/`requestSyncRow`/
    `requestClearRow` calls without reaching into this panel's internals.
    """

    rowActionRequested = Signal(str, str, str)  # action, symbol, interval

    def __init__(
        self,
        status_model: DatabaseStatusTableModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        ensure_qml_style()
        self.body_layout.setContentsMargins(12, 12, 12, 12)
        self.body_layout.setSpacing(8)

        self._vm = DatabaseStatusVM(status_model, parent=self)
        self._vm.rowActionRequested.connect(self.rowActionRequested)

        self._quick = QQuickWidget()
        self._quick.setObjectName("databaseStatusQuick")
        self._quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        # Transparent so this `Panel`'s own SURFACE background shows behind
        # the QML body — same reasoning `QmlOverlay.__init__` documents for
        # its own `QQuickWidget`.
        self._quick.setClearColor(Qt.GlobalColor.transparent)
        root_context = self._quick.rootContext()
        root_context.setContextProperty("vm", self._vm)
        # A QML context property is a borrowed pointer, and this bridge is
        # process-wide — but `get_theme_bridge()` is not something a bare
        # embedded `QQuickWidget` gets seeded with for free the way a
        # `QmlHostView`-driven screen does, so it is set explicitly here,
        # matching `QmlOverlay.__init__` (`qml/host.py`).
        root_context.setContextProperty("Theme", get_theme_bridge())

        self._quick.setSource(QUrl.fromLocalFile(str(_QML)))
        if self._quick.status() is not QQuickWidget.Status.Ready:
            raise RuntimeError(
                f"QML failed to load: {_QML}\n"
                + "\n".join(error.toString() for error in self._quick.errors())
            )
        self.body_layout.addWidget(self._quick, 1)

    def set_search_text(self, text: str) -> None:
        self._vm.setSearchText(text)

    def set_actions_enabled(self, enabled: bool) -> None:
        self._vm.setActionsEnabled(enabled)

    @property
    def root_object(self) -> QObject:
        """The loaded QML root, for tests to `findChild`/`qml_item` into by
        `objectName` — same contract `QmlOverlay.root_object` documents."""
        root = self._quick.rootObject()
        if root is None:  # pragma: no cover - __init__ raises before this
            raise RuntimeError("QML root object is missing")
        return root
