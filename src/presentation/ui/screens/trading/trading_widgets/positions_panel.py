"""Embeds `PositionsTable.qml` inline in the Trading screen's workspace.

@details Same shape `DatabaseStatusPanel` uses for `DatabaseStatusTable.qml`
(`EPIC-015` Phase 2): a `QQuickWidget` hosted directly on a `kit.Panel`,
not through `QmlOverlay` (this is not a dialog).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Panel
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_vm import (
    PositionsVM,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.style import ensure_qml_style
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

_QML = (
    Path(__file__).resolve().parents[3]
    / "qml"
    / "PositionsTable"
    / "PositionsTable.qml"
)


class PositionsPanel(Panel):
    """The Positions table, embedded (not modal)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ensure_qml_style()
        self.body_layout.setContentsMargins(12, 12, 12, 12)
        self.body_layout.setSpacing(8)

        self._vm = PositionsVM(parent=self)

        self._quick = QQuickWidget()
        self._quick.setObjectName("positionsTableQuick")
        self._quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self._quick.setClearColor(Qt.GlobalColor.transparent)
        root_context = self._quick.rootContext()
        root_context.setContextProperty("vm", self._vm)
        root_context.setContextProperty("Theme", get_theme_bridge())

        self._quick.setSource(QUrl.fromLocalFile(str(_QML)))
        if self._quick.status() is not QQuickWidget.Status.Ready:
            raise RuntimeError(
                f"QML failed to load: {_QML}\n"
                + "\n".join(error.toString() for error in self._quick.errors())
            )
        self.body_layout.addWidget(self._quick, 1)

    def set_rows(self, rows: list[PositionRow]) -> None:
        self._vm.set_rows(rows)

    @property
    def root_object(self) -> QObject:
        """The loaded QML root, for tests to `findChild`/`qml_item` into by
        `objectName` — same contract `DatabaseStatusPanel.root_object`
        documents."""
        root = self._quick.rootObject()
        if root is None:  # pragma: no cover - __init__ raises before this
            raise RuntimeError("QML root object is missing")
        return root
