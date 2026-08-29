"""Thin render and interaction tests for the standalone QML component."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QPoint, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtTest import QTest
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SymbolPicker.symbol_picker_theme import (
    SymbolPickerTheme,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SymbolPicker.symbol_picker_vm import (
    SymbolPickerVM,
)

from .test_symbol_picker_vm import _Source

_QML = Path(__file__).resolve().parents[1] / "SymbolPicker.qml"


def _walk(item):
    for child in item.childItems():
        yield child
        yield from _walk(child)


def _load(qapp, source=None):
    vm = SymbolPickerVM(source or _Source())
    vm.refresh()
    quick = QQuickWidget()
    theme = SymbolPickerTheme()
    # QML context properties are borrowed references; keep both objects alive
    # for the complete scene lifetime just like a real standalone host does.
    quick._symbol_picker_vm = vm
    quick._symbol_picker_theme = theme
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.setSource(QUrl.fromLocalFile(str(_QML)))
    assert quick.status() is QQuickWidget.Status.Ready, quick.errors()
    root = quick.rootObject()
    root.setProperty("vm", vm)
    root.setProperty("theme", theme)
    quick.resize(720, 620)
    root.openPicker()
    quick.show()
    qapp.processEvents()
    popup = root.findChild(QObject, "symbolPicker")
    return quick, popup, vm


def _popup_root(popup):
    # `Popup` relocates its rendered content onto the window's Overlay layer
    # once opened, so `childItems()` walked from the outer host `root` no
    # longer reaches it (qml-rule.md §0.1/§7) — search from the popup's own
    # `contentItem` instead.
    return popup.property("contentItem")


def test_component_loads_without_qml_overlay_or_app_bootstrap(qapp, qml_item):
    quick, popup, _vm = _load(qapp)

    assert popup is not None
    assert popup.property("visible") is True
    assert qml_item(_popup_root(popup), "txtSymbolSearch") is not None
    quick.close()
    quick.deleteLater()


def test_component_renders_one_card_per_visible_row(qapp, qml_item):
    quick, popup, _vm = _load(qapp)
    content = _popup_root(popup)

    cards = [
        item
        for name in (
            "symbolStar_ETHUSDT",
            "symbolStar_ETHBTC",
            "symbolStar_ETHEUR",
            "symbolStar_AAVEETH",
        )
        if (item := qml_item(content, name)) is not None
    ]
    assert len(cards) == 4
    quick.close()
    quick.deleteLater()


def test_real_text_input_reaches_the_vm(qapp, qml_item):
    quick, popup, vm = _load(qapp)
    field = qml_item(_popup_root(popup), "txtSymbolSearch")
    field.forceActiveFocus()
    QTest.keyClicks(quick, "btc")
    qapp.processEvents()

    assert vm.query == "btc"
    assert vm.resultCount == 1
    quick.close()
    quick.deleteLater()


def test_real_card_click_emits_symbol_and_closes_component(qapp, qml_item):
    quick, popup, vm = _load(qapp)
    chosen: list[str] = []
    vm.symbolChosen.connect(chosen.append)
    card_star = qml_item(_popup_root(popup), "symbolStar_ETHBTC")
    card = card_star.parentItem()
    point = card.mapToScene(card.boundingRect().center())
    QTest.mouseClick(
        quick,
        Qt.MouseButton.LeftButton,
        pos=QPoint(int(point.x()), int(point.y())),
    )
    qapp.processEvents()

    assert chosen == ["ETHBTC"]
    assert popup.property("visible") is False
    quick.close()
    quick.deleteLater()


def test_grid_view_virtualizes_1000_result_delegates(qapp, qml_item):
    symbols = tuple(f"COIN{index}USDT" for index in range(1000))
    quick, popup, _vm = _load(qapp, _Source(symbols=symbols, favourites=()))
    content = _popup_root(popup)
    result_grid = qml_item(content, "symbolResultGrid")
    qapp.processEvents()

    delegates = [
        item for item in _walk(content) if item.objectName().startswith("symbolCard_")
    ]
    assert result_grid.property("count") == 1000
    assert len(delegates) < 100
    quick.close()
    quick.deleteLater()


def test_star_click_toggles_favourite_without_selecting_symbol(qapp, qml_item):
    quick, popup, vm = _load(qapp)
    chosen: list[str] = []
    starred: list[str] = []
    vm.symbolChosen.connect(chosen.append)
    vm.favouriteToggled.connect(starred.append)
    star = qml_item(_popup_root(popup), "symbolStar_ETHUSDT")
    point = star.mapToScene(star.boundingRect().center())

    QTest.mouseClick(
        quick,
        Qt.MouseButton.LeftButton,
        pos=QPoint(int(point.x()), int(point.y())),
    )
    qapp.processEvents()

    assert chosen == []
    assert starred == ["ETHUSDT"]
    assert vm.rows[0]["favourite"] is True
    quick.close()
    quick.deleteLater()
