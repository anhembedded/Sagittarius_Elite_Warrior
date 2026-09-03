"""Thin render tests for `KlineInspectorTable.qml`.

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

from PySide6.QtCore import Property, QObject, QUrl
from PySide6.QtQuickWidgets import QQuickWidget

from .test_kline_inspector_vm import _vm

_QML = Path(__file__).resolve().parents[1] / "KlineInspectorTable.qml"


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
    def accent(self) -> str:
        return "#ff9900"  # token-exempt: fake theme double, not a real Palette value

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
    vm = vm or _vm()
    theme = _FakeTheme()
    quick = QQuickWidget()
    quick._kline_inspector_vm = vm
    quick._kline_inspector_theme = theme
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", theme)
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.setSource(QUrl.fromLocalFile(str(_QML)))
    assert quick.status() is QQuickWidget.Status.Ready, quick.errors()
    quick.resize(900, 420)
    quick.show()
    qapp.processEvents()
    return quick, quick.rootObject()


def test_component_loads_and_renders_the_subtitle(qapp, qml_item):
    quick, root = _load(qapp)

    assert root.objectName() == "klineInspectorBody"
    subtitle = qml_item(root, "lblKlineInspectorSubtitle")
    assert subtitle.property("text") == "BTCUSDT (1m)  •  2 nến"
    quick.close()
    quick.deleteLater()


def test_rows_render_and_colour_by_bullish_state(qapp, qml_item):
    vm = _vm()
    quick, root = _load(qapp, vm)

    bullish_ts = vm.rows[0]["timestampMs"]
    bearish_ts = vm.rows[1]["timestampMs"]
    close_up = qml_item(root, f"klineClose_{bullish_ts}")
    close_down = qml_item(root, f"klineClose_{bearish_ts}")
    assert close_up is not None
    assert close_down is not None
    assert close_up.property("color") != close_down.property("color")
    quick.close()
    quick.deleteLater()


def test_empty_candle_list_shows_the_empty_label(qapp, qml_item):
    empty_vm = _vm(candles=())
    quick, root = _load(qapp, empty_vm)

    empty_label = qml_item(root, "lblKlineInspectorEmpty")
    assert empty_label.property("visible") is True
    quick.close()
    quick.deleteLater()


def test_the_vm_becoming_null_after_load_does_not_throw(qapp):
    """Same defect class as `PositionsTable`/`OpenOrdersTable`'s own tests
    (real shutdown log evidence there): `KlineInspectorDialogWidget`'s
    `KlineInspectorVM` is a `QObject` that can be destroyed before its
    `QQuickWidget`'s QML engine is, at which point Qt Quick sets the `vm`
    context property to `null` and every live binding referencing it
    re-evaluates — the subtitle text, `rowsModel`, and `isEmpty` all read
    `vm.*` with no null guard."""
    from PySide6.QtCore import qInstallMessageHandler

    vm = _vm()
    quick, _root = _load(qapp, vm)

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
