"""Thin render and interaction tests for `TimeframeToolbar.qml` and
`TimeframePicker.qml`.

Loads each file directly into a bare `QQuickWidget` with hand-set `vm`/
`Theme` context properties, sidestepping `QmlOverlay` (see NOTES.md — that
pulls in `sagittarius_engine`, a separate repo not always present in a dev
environment). A real host still goes through `QmlOverlay` normally; this
file only proves the `.qml` loads and its bindings point at properties the
VM actually has.
"""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtTest import QTest

from .test_timeframe_vm import _vm

_TOOLBAR_QML = Path(__file__).resolve().parents[1] / "TimeframeToolbar.qml"
_PICKER_QML = Path(__file__).resolve().parents[1] / "TimeframePicker.qml"


class _FakeTheme(QObject):
    """Minimal token set these `.qml` files read — a local double, not
    `SymbolPickerTheme`, so this widget's tests do not depend on another
    widget's directory (conftest.py's rule)."""

    @Property(str, constant=True)
    def bg(self) -> str:
        return "#111111"  # token-exempt: fake theme double, not a real Palette value

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
    def stateIdleBg(self) -> str:
        return "#1a1a1a"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateActiveTint(self) -> str:
        return "#33ff9926"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateNavBorder(self) -> str:
        return "#444444"  # token-exempt: fake theme double, not a real Palette value


def _load(qapp, qml_file: Path, vm=None):
    vm = vm or _vm()[0]
    theme = _FakeTheme()
    quick = QQuickWidget()
    quick._timeframe_vm = vm
    quick._timeframe_theme = theme
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", theme)
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.setSource(QUrl.fromLocalFile(str(qml_file)))
    assert quick.status() is QQuickWidget.Status.Ready, quick.errors()
    quick.resize(640, 420)
    quick.show()
    qapp.processEvents()
    return quick, quick.rootObject(), vm


def test_toolbar_loads_and_renders_one_pill_per_pinned_code(qapp, qml_item):
    quick, root, _ = _load(qapp, _TOOLBAR_QML)

    assert root.objectName() == "timeframeToolbar"
    for code in ("1m", "5m", "15m", "1h", "1d"):
        assert qml_item(root, f"timeframePill_{code}") is not None
    assert qml_item(root, "btnTimeframeMore") is not None
    quick.close()
    quick.deleteLater()


def test_clicking_a_pill_reaches_the_vm(qapp, qml_item):
    quick, root, vm = _load(qapp, _TOOLBAR_QML)
    chosen: list[str] = []
    vm.chosen.connect(chosen.append)
    pill = qml_item(root, "timeframePill_15m")
    point = pill.mapToScene(pill.boundingRect().center())

    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()

    assert chosen == ["15m"]
    quick.close()
    quick.deleteLater()


def test_clicking_more_emits_the_toolbars_own_signal_not_the_vm(qapp, qml_item):
    quick, root, vm = _load(qapp, _TOOLBAR_QML)
    chosen: list[str] = []
    more_clicks: list[None] = []
    vm.chosen.connect(chosen.append)
    root.moreRequested.connect(lambda: more_clicks.append(None))
    button = qml_item(root, "btnTimeframeMore")
    point = button.mapToScene(button.boundingRect().center())

    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()

    assert more_clicks == [None]
    assert chosen == []
    quick.close()
    quick.deleteLater()


def test_picker_loads_and_renders_one_card_per_offered_timeframe(qapp, qml_item):
    quick, root, _ = _load(qapp, _PICKER_QML)

    assert root.objectName() == "timeframePickerBody"
    for code in ("1s", "1m", "5m", "1h", "1d", "1M"):
        assert qml_item(root, f"timeframeCard_{code}") is not None
    quick.close()
    quick.deleteLater()


def test_clicking_a_card_chooses_it(qapp, qml_item):
    quick, root, vm = _load(qapp, _PICKER_QML)
    chosen: list[str] = []
    vm.chosen.connect(chosen.append)
    card = qml_item(root, "timeframeCard_4h")
    point = card.mapToScene(card.boundingRect().center())

    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()

    assert chosen == ["4h"]
    quick.close()
    quick.deleteLater()


def test_clicking_the_star_pins_without_choosing(qapp, qml_item):
    vm, state = _vm(pinned=())
    quick, root, _ = _load(qapp, _PICKER_QML, vm)
    chosen: list[str] = []
    vm.chosen.connect(chosen.append)
    star = qml_item(root, "timeframeStar_4h")
    point = star.mapToScene(star.boundingRect().center())

    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()

    assert chosen == []
    assert state["set_calls"] == [("4h", True)]
    assert any(row["code"] == "4h" for row in vm.pinnedRows)
    quick.close()
    quick.deleteLater()
