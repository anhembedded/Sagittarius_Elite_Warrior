"""Thin render and interaction tests for `TradeLogTable.qml`.

Loads the file directly into a bare `QQuickWidget` with hand-set `vm`/
`Theme` context properties, sidestepping `QmlOverlay` (see NOTES.md — that
pulls in `sagittarius_engine`, a separate repo not always present in a dev
environment). A real host still goes through `QmlOverlay`-style hosting
normally; this file only proves the `.qml` loads and its bindings point at
properties the VM actually has.
"""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtTest import QTest

from .test_trade_log_vm import _vm

_QML = Path(__file__).resolve().parents[1] / "TradeLogTable.qml"


class _FakeTheme(QObject):
    """Minimal token set this `.qml` reads — a local double, not another
    widget's theme class, so this widget's tests do not depend on another
    widget's directory (conftest.py's rule)."""

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

    @Property(str, constant=True)
    def stateActiveTint(self) -> str:
        return "#33ff9926"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateHoverBg(self) -> str:
        return "#2d2d2d"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateNavBorder(self) -> str:
        return "#444444"  # token-exempt: fake theme double, not a real Palette value


def _load(qapp, vm=None):
    vm = vm or _vm()
    theme = _FakeTheme()
    quick = QQuickWidget()
    quick._trade_log_vm = vm
    quick._trade_log_theme = theme
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", theme)
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.setSource(QUrl.fromLocalFile(str(_QML)))
    assert quick.status() is QQuickWidget.Status.Ready, quick.errors()
    quick.resize(900, 420)
    quick.show()
    qapp.processEvents()
    return quick, quick.rootObject(), vm


def test_component_loads_and_renders_one_row_per_trade(qapp, qml_item):
    quick, root, _ = _load(qapp)

    assert root.objectName() == "tradeLogBody"
    for index in range(1, 7):
        assert qml_item(root, f"tradeLogPositionLabel_{index}") is not None
    quick.close()
    quick.deleteLater()


def test_filter_tabs_render_with_counts(qapp, qml_item):
    quick, root, _ = _load(qapp)

    for tab_id in ("all", "long", "short", "win", "loss"):
        assert qml_item(root, f"tabTradeLogFilter_{tab_id}") is not None
    quick.close()
    quick.deleteLater()


def test_clicking_a_filter_tab_narrows_the_rendered_rows(qapp, qml_item):
    quick, root, _ = _load(qapp)
    tab = qml_item(root, "tabTradeLogFilter_short")
    point = tab.mapToScene(tab.boundingRect().center())

    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()

    assert qml_item(root, "tradeLogPositionLabel_1") is None
    assert qml_item(root, "tradeLogPositionLabel_5") is not None
    assert qml_item(root, "tradeLogPositionLabel_6") is not None
    quick.close()
    quick.deleteLater()


def test_pnl_and_return_text_render_for_each_row(qapp, qml_item):
    quick, root, _ = _load(qapp)

    pnl = qml_item(root, "tradeLogPnl_1")
    ret = qml_item(root, "tradeLogReturn_1")
    assert pnl.property("text") != ""
    assert ret.property("text") != ""
    quick.close()
    quick.deleteLater()


def test_expand_section_is_collapsed_until_clicked(qapp, qml_item):
    quick, root, _ = _load(qapp)

    assert qml_item(root, "tradeLogExpand_1").property("visible") is False
    quick.close()
    quick.deleteLater()


def test_clicking_the_row_reveals_entry_and_exit_reason(qapp, qml_item):
    quick, root, vm = _load(qapp)
    chevron = qml_item(root, "tradeLogChevron_1")
    point = chevron.mapToScene(chevron.boundingRect().center())

    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()

    assert qml_item(root, "tradeLogExpand_1").property("visible") is True
    assert vm.rows[0]["expanded"] is True
    quick.close()
    quick.deleteLater()


def test_clicking_an_expanded_row_again_collapses_it(qapp, qml_item):
    quick, root, _ = _load(qapp)
    chevron = qml_item(root, "tradeLogChevron_1")
    point = chevron.mapToScene(chevron.boundingRect().center())

    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()
    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()

    assert qml_item(root, "tradeLogExpand_1").property("visible") is False
    quick.close()
    quick.deleteLater()


def test_the_vm_becoming_null_after_load_does_not_throw(qapp):
    """Same defect class as `PositionsTable`/`OpenOrdersTable`/
    `KlineInspectorTable`'s own tests (real shutdown log evidence for the
    first two): whatever eventually hosts `TradeLogTable.qml` in
    production, its `TradeLogVM` is a `QObject` that can be destroyed
    before its `QQuickWidget`'s QML engine is, at which point Qt Quick
    sets the `vm` context property to `null` and every live binding
    referencing it re-evaluates — the filter tabs' `model`, the tab
    click handler, `rowsModel`, and `isEmpty` all read `vm.*` with no
    null guard."""
    from PySide6.QtCore import qInstallMessageHandler

    vm = _vm()
    quick, _root, _ = _load(qapp, vm)

    messages: list[str] = []
    previous_handler = qInstallMessageHandler(
        lambda mode, ctx, msg: messages.append(msg)
    )
    try:
        quick.rootContext().setContextProperty("vm", None)
        qapp.processEvents()
    finally:
        qInstallMessageHandler(previous_handler)

    assert not any("TypeError" in m for m in messages), messages
    quick.close()
    quick.deleteLater()
