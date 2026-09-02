"""Thin render tests for `OpenOrdersTable.qml` — same shape as
`PositionsTable`'s own QML test."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_orders_vm import (
    OpenOrdersVM,
)

from .test_open_orders_vm import _order

_QML = Path(__file__).resolve().parents[1] / "OpenOrdersTable.qml"


class _FakeTheme(QObject):
    """Minimal token set this `.qml` reads — a local double (conftest.py's
    rule: no cross-widget imports)."""

    @Property(str, constant=True)
    def textPrimary(self) -> str:
        return "#eeeeee"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def muted(self) -> str:
        return "#999999"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def border(self) -> str:
        return "#333333"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def success(self) -> str:
        return "#33cc66"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def danger(self) -> str:
        return "#cc3333"  # token-exempt: fake theme double, not a real Palette value


def _load(qapp, vm=None):
    vm = vm or OpenOrdersVM()
    theme = _FakeTheme()
    quick = QQuickWidget()
    quick._open_orders_vm = vm
    quick._open_orders_theme = theme
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", theme)
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.setSource(QUrl.fromLocalFile(str(_QML)))
    assert quick.status() is QQuickWidget.Status.Ready, quick.errors()
    quick.resize(760, 320)
    quick.show()
    qapp.processEvents()
    return quick, quick.rootObject(), vm


def test_component_loads_empty(qapp) -> None:
    quick, root, _ = _load(qapp)

    assert root.objectName() == "openOrdersTableBody"
    quick.close()
    quick.deleteLater()


def test_renders_one_row_per_order(qapp, qml_item) -> None:
    vm = OpenOrdersVM()
    vm.set_rows(
        [
            build_open_order_row(_order("BTCUSDT")),
            build_open_order_row(_order("ETHUSDT")),
        ]
    )
    quick, root, _ = _load(qapp, vm)

    assert qml_item(root, "openOrderSymbol_1") is not None
    assert qml_item(root, "openOrderSymbol_2") is not None
    assert qml_item(root, "openOrderSymbol_1").property("text") == "BTCUSDT"
    quick.close()
    quick.deleteLater()


def test_empty_state_shows_when_no_orders(qapp, qml_item) -> None:
    quick, root, _ = _load(qapp)

    empty_label = qml_item(root, "lblOpenOrdersEmpty")
    assert empty_label is not None
    assert empty_label.property("visible") is True
    quick.close()
    quick.deleteLater()
