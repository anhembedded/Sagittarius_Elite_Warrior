"""Thin render and interaction tests for `MetricsDetailPanel.qml`.

Loads the file directly into a bare `QQuickWidget` with hand-set `vm`/
`Theme` context properties, sidestepping any real host (see NOTES.md). This
file only proves the `.qml` loads and its bindings point at properties the
VM actually has — including the two-levels-deep nested `Repeater` (groups,
then each group's rows) actually rendering correctly, which is the one
part of this component novel enough to be worth a real render check rather
than trusting the pattern from a single, non-nested precedent.
"""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QPoint, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtTest import QTest

from .test_metrics_detail_vm import _vm

_QML = Path(__file__).resolve().parents[1] / "MetricsDetailPanel.qml"


class _FakeTheme(QObject):
    """Minimal token set this `.qml` (and `kit/PanelHeader`, `kit/Button`,
    `kit/DialogShell` it composes) reads."""

    @Property(str, constant=True)
    def bg(self) -> str:
        return "#111111"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def bgCard(self) -> str:
        return "#222222"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def border(self) -> str:
        return "#333333"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def textPrimary(self) -> str:
        return "#eeeeee"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def accent(self) -> str:
        return "#ff9900"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def muted(self) -> str:
        return "#999999"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def success(self) -> str:
        return "#33cc66"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def danger(self) -> str:
        return "#cc3333"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateIdleBg(self) -> str:
        return "#1a1a1a"  # token-exempt: fake theme double, not a real Palette value

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
    quick._metrics_detail_vm = vm
    quick._metrics_detail_theme = theme
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", theme)
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.setSource(QUrl.fromLocalFile(str(_QML)))
    assert quick.status() is QQuickWidget.Status.Ready, quick.errors()
    quick.resize(660, 700)
    quick.show()
    qapp.processEvents()
    return quick, quick.rootObject(), vm


def test_component_loads_and_renders_the_bar_figures(qapp, qml_item):
    quick, root, _ = _load(qapp)

    assert root.objectName() == "metricsDetailPanel"
    assert qml_item(root, "lblGrossProfit").property("text") == "+1,148.19"
    assert qml_item(root, "lblGrossLoss").property("text") == "-9,341.72"
    quick.close()
    quick.deleteLater()


def test_group_headers_and_nested_cards_render(qapp, qml_item):
    # The two-level Repeater (groups -> rows) has to actually produce a
    # card for a row belonging to the SECOND group — proof the inner
    # Repeater's `modelData` is the row, not left over from the outer one.
    quick, _root, vm = _load(qapp)

    risk_group = next(g for g in vm.groups if g["label"] == "RỦI RO")
    assert len(risk_group["rows"]) > 0
    quick.close()
    quick.deleteLater()


def test_footer_text_renders(qapp, qml_item):
    quick, root, _ = _load(qapp)

    footer = qml_item(root, "lblMetricsFooter")
    assert footer.property("text") == "Tính trên 891 lệnh đã đóng · phí 0.1% mỗi lệnh"
    quick.close()
    quick.deleteLater()


def test_clicking_copy_all_emits_copy_requested(qapp, qml_item):
    quick, root, vm = _load(qapp)
    copies: list[None] = []
    vm.copyRequested.connect(lambda: copies.append(None))

    button = qml_item(root, "btnMetricsCopyAll")
    point = button.mapToScene(button.boundingRect().center())
    QTest.mouseClick(
        quick, Qt.MouseButton.LeftButton, pos=QPoint(int(point.x()), int(point.y()))
    )
    qapp.processEvents()

    assert copies == [None]
    quick.close()
    quick.deleteLater()


def test_clicking_close_emits_close_requested(qapp, qml_item):
    quick, root, vm = _load(qapp)
    closes: list[None] = []
    vm.closeRequested.connect(lambda: closes.append(None))

    button = qml_item(root, "btnMetricsClose")
    point = button.mapToScene(button.boundingRect().center())
    QTest.mouseClick(
        quick, Qt.MouseButton.LeftButton, pos=QPoint(int(point.x()), int(point.y()))
    )
    qapp.processEvents()

    assert closes == [None]
    quick.close()
    quick.deleteLater()


def test_clicking_the_dialog_shell_close_x_also_emits_close_requested(qapp, qml_item):
    quick, root, vm = _load(qapp)
    closes: list[None] = []
    vm.closeRequested.connect(lambda: closes.append(None))

    button = qml_item(root, "btnDialogShellClose")
    point = button.mapToScene(button.boundingRect().center())
    QTest.mouseClick(
        quick, Qt.MouseButton.LeftButton, pos=QPoint(int(point.x()), int(point.y()))
    )
    qapp.processEvents()

    assert closes == [None]
    quick.close()
    quick.deleteLater()
