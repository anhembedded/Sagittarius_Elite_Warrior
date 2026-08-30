"""`MetricsDetailModal` — a real, app-modal `QDialog` hosting
`MetricsDetailPanel.qml`.

@par Why not `QmlOverlay`
`MetricsDetailPanel.qml`'s root is `kit/DialogShell`, not a bare body: it
already renders its own header (accent mark, title, × close) and its own
footer ("Copy tất cả" ghost + "Đóng" primary) — see
`MetricsDetailPanel.qml`'s own top comment and `NOTES.md`'s "Self-contained
via `kit/DialogShell`, not `QmlOverlay`" section. Wrapping that in
`QmlOverlay` (`qml/host.py`) would stack a second title/subtitle row and a
second footer button row above chrome the `.qml` already draws — the exact
"Forcing it through `QmlOverlay` would stack a second title label..."
problem `symbol_picker_modal_host.py` names for `SymbolPicker.qml`.

@par Why this is NOT the same problem `SymbolPickerModal` solves
`SymbolPickerModal` exists because `SymbolPicker.qml` draws its own `Popup`,
and a `Popup` can only dim/block the `Window` it lives in (its own
`QQuickWidget`), never the QtWidgets screen around it — so *something*
QtWidgets-modal had to contain it regardless of chrome. `DialogShell` is the
mirror image: `kit/DialogShell.qml`'s own top comment says plainly it is "for
the day a whole route is QML" — a plain `ColumnLayout`, not a `Popup`/`Dialog`,
with **no** dim/block mechanism of its own at all. So this host is not
working around a `Popup`'s reach; it is supplying the modality that never
existed in the first place. The reason both hosts still end up the same
shape — a real `QDialog`, no `Overlay` chrome, `ensure_qml_style()`,
load-or-raise — is that both `.qml` files draw their own complete header and
footer, leaving nothing for `Overlay` to usefully add.

@par Lifecycle
Simpler than `SymbolPickerModal`'s: there is no inner `Popup` to race against.
`DialogShell.cancelled()` fires from the × button (`onCancelled:
vm.requestClose()` in `MetricsDetailPanel.qml`), and `MetricsDetailVM.requestClose()`
(a `@Slot()` also called by the "Đóng" footer button) re-emits it as the
plain Qt `closeRequested` signal — so connecting that one signal to
`self.close()` covers every way this dialog can be asked to close. No
`showEvent()` override re-fetches on open the way `SymbolPickerModal` does:
`MetricsDetailVM.refresh()` is not idempotent-on-open by itself (it has no
"already open" state to reset), so re-running it belongs to whichever caller
knows when the underlying data changed — `MetricsDetailDialogWidget`
connects it to `BackTestViewModel.statCardsChanged` instead of hooking
`showEvent()`, so a snapshot arriving while the dialog is not yet open is not
silently missed.

@par The "Copy tất cả" button
`MetricsDetailVM.copyRequested` had no listener before this host — `NOTES.md`
named it a "structural pass" gap. Handled here, not in a screen's
composition root, because it needs nothing screen-specific: `vm.groups` plus
the 4 summary strings (`grossProfitText`/`grossLossText`/`barCaption`/
`footerText`) are already everything `MetricsDetailVM` computed, and turning
them into one plain-text block is the same shape any future host of this
component would want. Mirrors the one existing "copy a readout to the
clipboard" precedent in this app,
`sagittarius_engine`'s `LogListModel.copyAllToClipboard()`
(`extensions/pyside_mvc/runtime/log_list_model.py`): build one `str`, hand it
straight to `QGuiApplication.clipboard().setText(...)`, no intermediate
widget selection required of the user.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

from ..style import ensure_qml_style
from .metrics_detail_vm import MetricsDetailVM

_QML_FILE = Path(__file__).with_name("MetricsDetailPanel.qml")
_WIDTH = 660
_HEIGHT = 700


def _format_row(row: dict[str, object]) -> str:
    suffix = f" {row['suffix']}" if row["suffix"] else ""
    badge = f" [{row['badgeText']}]" if row["badgeText"] else ""
    info = f" ({row['infoBadge']})" if row["infoBadge"] else ""
    return f"  {row['title']}: {row['value']}{suffix}{badge}{info}"


def _build_clipboard_text(vm: MetricsDetailVM) -> str:
    """One plain-text dump of every group/row plus the summary strings —
    `NOTES.md`'s "Copy tất cả" gap, closed. Same idea as
    `LogListModel.copyAllToClipboard()`: readable as plain text, no markup,
    safe to paste into a chat message or a bug report."""
    lines = [
        "CHỈ SỐ CHI TIẾT BACKTEST",
        f"Lãi thô {vm.grossProfitText} / Lỗ thô {vm.grossLossText}",
        vm.barCaption,
        "",
    ]
    for group in vm.groups:
        lines.append(str(group["label"]))
        lines.extend(_format_row(row) for row in group["rows"])
        lines.append("")
    lines.append(vm.footerText)
    return "\n".join(lines)


class MetricsDetailModal(QDialog):  # base-exempt: .qml draws its own DialogShell chrome
    """
    @brief App-modal `QDialog` shell around `MetricsDetailPanel.qml`.

    @param vm The widget ViewModel — a caller builds this against its own
        seven `get_*` callbacks (`MetricsDetailVM.__init__`) before
        constructing the modal, then calls `vm.refresh()` at least once
        (this class does not call it automatically — see class docstring).
    """

    def __init__(
        self,
        vm: MetricsDetailVM,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("metricsDetailModal")
        self.setModal(True)
        self.resize(_WIDTH, _HEIGHT)
        ensure_qml_style()

        # Named `_widget_vm`, not `_vm` — same collision this repo already
        # hit once (see `SymbolPickerModal`'s docstring): a subclass's own
        # screen ViewModel needs `self._vm` free.
        self._widget_vm = vm

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._quick = QQuickWidget()
        self._quick.setObjectName("qmlBody")
        self._quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self._quick.setClearColor(Qt.GlobalColor.transparent)

        # Context properties are borrowed references; held on `self` (not
        # just passed through) so Python keeps them alive as long as the
        # QML scene can read them — same reasoning `QmlOverlay.__init__` and
        # `SymbolPickerModal.__init__` both document.
        self._theme = get_theme_bridge()
        root_context = self._quick.rootContext()
        root_context.setContextProperty("vm", self._widget_vm)
        root_context.setContextProperty("Theme", self._theme)

        self._quick.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
        if self._quick.status() is not QQuickWidget.Status.Ready:
            raise RuntimeError(
                f"QML failed to load: {_QML_FILE}\n"
                + "\n".join(error.toString() for error in self._quick.errors())
            )
        layout.addWidget(self._quick, 1)

        root = self._quick.rootObject()
        if root is None:  # pragma: no cover - status check above already raises
            raise RuntimeError("MetricsDetailPanel QML root object is missing")
        self._root = root

        self._widget_vm.closeRequested.connect(self.close)
        self._widget_vm.copyRequested.connect(self._on_copy_requested)

    @property
    def root_object(self) -> object:
        """The loaded QML root, for tests to `findChild`/inspect by name."""
        return self._root

    def _on_copy_requested(self) -> None:
        QGuiApplication.clipboard().setText(_build_clipboard_text(self._widget_vm))
