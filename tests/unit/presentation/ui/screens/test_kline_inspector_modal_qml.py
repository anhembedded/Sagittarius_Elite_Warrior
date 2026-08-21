"""
Regression test for BUG-028: KLineInspectorModal column width scope.
Proves that column widths are declared directly on the modal root object
and do not evaluate to undefined.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlComponent
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from sagittarius_engine.extensions.pyside_mvc import (
    configure_app_qml,
    create_quick_widget,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = Path(__file__).resolve().parents[5]
_UI_DIR = _REPO_ROOT / "src" / "presentation" / "ui"
_MODAL_FILE = _UI_DIR / "screens" / "data_management" / "KLineInspectorModal.qml"


def test_kline_inspector_modal_root_exposes_column_widths(qapp):
    """
    BUG-028 regression test:
    Column widths must be declared at the modal root so bindings like `root.colTimeWidth`
    do not evaluate to undefined / fail type coercion to double.
    """
    configure_app_qml(Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict())
    widget = create_quick_widget()
    engine = widget.engine()
    engine.addImportPath(str(_UI_DIR))
    engine.addImportPath(str(_UI_DIR / "components"))

    component = QQmlComponent(engine, QUrl.fromLocalFile(str(_MODAL_FILE)))
    assert component.status() == QQmlComponent.Status.Ready, [
        e.toString() for e in component.errors()
    ]
    modal = component.create()
    assert modal is not None

    try:
        col_time = modal.property("colTimeWidth")
        col_price = modal.property("colPriceWidth")
        col_vol = modal.property("colVolWidth")
        col_change = modal.property("colChangeWidth")
        col_trades = modal.property("colTradesWidth")

        assert col_time is not None, "colTimeWidth is undefined on root (BUG-028)"
        assert col_price is not None, "colPriceWidth is undefined on root (BUG-028)"
        assert col_vol is not None, "colVolWidth is undefined on root (BUG-028)"
        assert col_change is not None, "colChangeWidth is undefined on root (BUG-028)"
        assert col_trades is not None, "colTradesWidth is undefined on root (BUG-028)"

        assert col_time == 140.0
        assert col_price == 80.0
        assert col_vol == 105.0
        assert col_change == 75.0
        assert col_trades == 70.0
    finally:
        modal.deleteLater()
