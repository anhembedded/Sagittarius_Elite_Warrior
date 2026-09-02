"""Embeds `OpenOrdersTable.qml` inline in the Trading screen's workspace.

@details Same shape as `PositionsPanel`/`DatabaseStatusPanel`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Panel
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_orders_vm import (
    OpenOrdersVM,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.style import ensure_qml_style
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

_QML = (
    Path(__file__).resolve().parents[3]
    / "qml"
    / "OpenOrdersTable"
    / "OpenOrdersTable.qml"
)


class OpenOrdersPanel(Panel):
    """The Open Orders table, embedded (not modal)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ensure_qml_style()
        self.body_layout.setContentsMargins(12, 12, 12, 12)
        self.body_layout.setSpacing(8)

        self._vm = OpenOrdersVM(parent=self)

        self._quick = QQuickWidget()
        self._quick.setObjectName("openOrdersTableQuick")
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

    def set_rows(self, rows: list[OpenOrderRow]) -> None:
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
