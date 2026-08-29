"""Standalone live preview for the SymbolPicker QML component."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.interfaces.i_symbol_picker_source import (
    ISymbolPickerSource,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SymbolPicker.symbol_picker_theme import (
    SymbolPickerTheme,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SymbolPicker.symbol_picker_vm import (
    SymbolPickerVM,
)

_QML_FILE = Path(__file__).with_name("SymbolPicker.qml")


class _PreviewSource(ISymbolPickerSource):
    """Small deterministic source used only by the live preview harness."""

    _SYMBOLS = (
        "ETHUSDT",
        "ETHBTC",
        "ETHEUR",
        "AAVEETH",
        "ADAETH",
        "ARBETH",
        "BNBETH",
        "ETHARS",
        "ETHBRL",
        "ETHFDUSD",
        "ETHFITRY",
        "ETHIDR",
        "ETHJPY",
        "ETHMXN",
    )

    def get_symbols(self) -> Sequence[str]:
        return self._SYMBOLS

    def get_favourites(self) -> Sequence[str]:
        return ("ETHBTC", "ETHUSDT")

    def get_recents(self) -> Sequence[str]:
        return ("ETHEUR", "ETHFDUSD")

    def get_current(self) -> str:
        return "ETHUSDT"

    def set_favourite(self, symbol: str, favourite: bool) -> None:
        pass


def build_preview() -> QWidget:
    """Build the SymbolPicker without an app modal or application ViewModel."""
    quick = QQuickWidget()
    quick.setObjectName("symbolPickerPreview")
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.setClearColor(Qt.GlobalColor.transparent)

    vm = SymbolPickerVM(_PreviewSource())
    vm.refresh()
    theme = SymbolPickerTheme()
    quick.rootContext().setContextProperty("symbolPickerPreviewVM", vm)
    quick.rootContext().setContextProperty("symbolPickerPreviewTheme", theme)
    # QML properties are borrowed references; retain both for the scene lifetime.
    quick._symbol_picker_vm = vm
    quick._symbol_picker_theme = theme

    quick.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
    if quick.status() is not QQuickWidget.Status.Ready:
        raise RuntimeError(
            f"QML failed to load: {_QML_FILE}\n"
            + "\n".join(error.toString() for error in quick.errors())
        )

    root = quick.rootObject()
    if root is None:  # pragma: no cover - guarded by the status check above
        raise RuntimeError("SymbolPicker QML root object is missing")
    root.setProperty("vm", vm)
    root.setProperty("theme", theme)
    root.openPicker()
    quick.resize(720, 620)
    return quick
