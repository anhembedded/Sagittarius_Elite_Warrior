"""`SymbolPickerModal` — a real, app-modal `QDialog` hosting `SymbolPicker.qml`.

@par Why not `QmlOverlay`
`qml-rule.md` §0.1 gives two correct modal-QML shapes. `QmlOverlay`
(`qml/host.py`) is the first: a real `QDialog` supplies title/subtitle chrome
and a footer button row, and the `.qml` inside is a plain body with no modal
of its own — five widgets already use it that way. `SymbolPicker.qml` does
not fit that shape: it draws its own header, search field, tabs and footer
*and* its own `Popup` (its `NOTES.md` explains why — the component must stay
usable outside this app, so it owns its whole modal surface). Forcing it
through `QmlOverlay` would stack a second title label and an empty footer
button row above content that already has both, and the base class has no
"no chrome" switch to turn that off.

What both shapes still agree on, and what actually matters here per §0.1's
own reasoning: `Popup`'s dim/block only reaches the `Window` it lives in, and
a `QQuickWidget` is its own `Window`, separate from any QtWidgets around it.
So whatever contains `SymbolPicker.qml` inside a QtWidgets screen (every
current caller) MUST itself be a real, application-modal `QDialog` — the
`Popup` cannot supply that on its own no matter how it is configured. This
class is exactly that shell and nothing more: a modal `QDialog`, the same
`ensure_qml_style()` pin and load-or-raise behaviour `QmlOverlay` uses, sized
to the picker's own 720x620 (`SymbolPicker.qml`'s `implicitWidth`/
`implicitHeight`). It carries no title, subtitle, or button row, because the
`.qml` already renders all three.

@par Lifecycle
`SymbolPicker.qml`'s own `openPicker()` resets its filter state and re-reads
the source (`AbstractSymbolPickerVM.refresh()`) before opening, the same
"refetch on every open" behaviour the old `SymbolPickerOverlay.showEvent()`
implemented by hand — so this host calls it from `showEvent()` once, instead
of every caller having to remember to.

Escape, click-outside, and the × button all close only the inner `Popup`
(the QML root's `dismissed()` signal fires once it does); left alone, the
outer `QDialog` would then sit on screen empty and unmodal-looking, since
`SymbolPicker.qml`'s root has nothing else to render once its `Popup` is
closed — so this host closes itself whenever `dismissed()` fires. Choosing a
symbol goes through the exact same path: the QML root closes its own
`Popup` right after emitting its `symbolChosen(string)` signal (see the
`.qml`'s `Connections` block), which fires `dismissed()` just the same — so
one connection closes this shell for every reason the inner `Popup` can
close, instead of two competing calls to `accept()`/`reject()` racing each
other. The *choice itself* — updating a screen's ViewModel, recording
"recently used" — is a caller decision; this class stays app-neutral by only
re-emitting the QML root's `symbolChosen` as a plain Qt `Signal(str)`,
without knowing what a caller does with the symbol name.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

from ..style import ensure_qml_style
from .symbol_picker_theme import SymbolPickerTheme
from .symbol_picker_vm import SymbolPickerVM

_QML_FILE = Path(__file__).with_name("SymbolPicker.qml")
_WIDTH = 720
_HEIGHT = 620


class SymbolPickerModal(QDialog):  # base-exempt: SymbolPicker.qml draws its own chrome
    """@brief App-modal `QDialog` shell around `SymbolPicker.qml`.

    @param vm The widget ViewModel — a caller builds this against its own
        `ISymbolPickerSource` implementation before constructing the modal.
    @param theme Optional token override. Defaults to `SymbolPickerTheme()`,
        the component's own tokens (already copied from this app's real
        `Palette`, see `symbol_picker_theme.py`) — a caller only needs to pass
        one if it wants different tokens, never to make the picker visible.
    """

    symbolChosen = Signal(str)

    def __init__(
        self,
        vm: SymbolPickerVM,
        theme: SymbolPickerTheme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("symbolPickerModal")
        self.setModal(True)
        self.resize(_WIDTH, _HEIGHT)
        ensure_qml_style()

        # Named `_widget_vm`, not `_vm` — `CapitalDialogWidget`'s convention,
        # and load-bearing here: a `SymbolPickerDialogWidget` subclass needs
        # `self._vm` free for its own *screen* ViewModel. This attribute
        # collided with that one until a test caught it (BUG-class this
        # repo's rules call out repeatedly — see `.agents/ONBOARDING.md` §8):
        # `self._vm = view_model` in the subclass's own `__init__`, running
        # *before* `super().__init__()`, was silently overwritten the moment
        # this base class's `__init__` ran its own `self._vm = vm` line,
        # because Python attribute assignment does not care which class
        # "owns" the name. The screen ViewModel update after a choice then
        # wrote through to the wrong object — no exception, since `vm` is a
        # `QObject` and Python allows setting an attribute Qt never declared
        # as a property; it just silently failed to update `selectedSymbol`.
        self._widget_vm = vm
        self._theme = theme if theme is not None else SymbolPickerTheme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._quick = QQuickWidget()
        self._quick.setObjectName("qmlBody")
        self._quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self._quick.setClearColor(Qt.GlobalColor.transparent)

        # Context properties are borrowed references; held on `self` (not
        # just passed through) for the same reason `QmlOverlay` holds its
        # `_context` dict — Python must keep them alive as long as the QML
        # scene can read them.
        root_context = self._quick.rootContext()
        root_context.setContextProperty("vm", self._widget_vm)
        root_context.setContextProperty("theme", self._theme)

        self._quick.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
        if self._quick.status() is not QQuickWidget.Status.Ready:
            raise RuntimeError(
                f"QML failed to load: {_QML_FILE}\n"
                + "\n".join(error.toString() for error in self._quick.errors())
            )
        layout.addWidget(self._quick, 1)

        root = self._quick.rootObject()
        if root is None:  # pragma: no cover - status check above already raises
            raise RuntimeError("SymbolPicker QML root object is missing")
        # `preview.py` sets both the context property AND the root property —
        # mirrored here for the same reason: a root-level `property var vm`
        # read before the context property is delivered would otherwise see
        # only the QML-declared fallback.
        root.setProperty("vm", self._widget_vm)
        root.setProperty("theme", self._theme)
        self._root = root

        root.symbolChosen.connect(self._on_symbol_chosen)
        # One connection closes this shell for every reason the inner
        # `Popup` can close (chosen, Escape, click-outside, ×) — see the
        # class docstring's "Lifecycle" section for why a second call to
        # accept()/reject() on the choice path would race this one.
        root.dismissed.connect(self.close)

    @property
    def root_object(self) -> QObject:
        """The loaded QML root, for tests to `findChild`/inspect by name."""
        return self._root

    def showEvent(self, event: QShowEvent) -> None:
        """Re-opens the picker on every show — see class docstring."""
        self._root.openPicker()
        super().showEvent(event)

    def _on_symbol_chosen(self, symbol: str) -> None:
        self.symbolChosen.emit(symbol)
