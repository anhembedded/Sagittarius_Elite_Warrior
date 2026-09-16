"""`ProgressBannerWidget` — a bare `QQuickWidget` embedding `ProgressBanner.qml` inline.

@par Why not `QmlOverlay` or `SymbolPickerModal`
`qml-rule.md` §0.1 names two *modal* QML shapes, both hosted by a real
`QDialog` because a `Popup`'s dim/block only reaches the `Window` it lives
in. Neither applies here: this widget is not modal at all — it sits inside
`DataManagementView`'s own `QVBoxLayout`, in the exact spot
`AppProgressBar` + a standalone Cancel `QPushButton` used to occupy
(`EPIC-015` Phase 2, the rollout's first non-modal, inline embed of a QML
panel into a screen's own layout). There is nothing to dim or block, so a
plain `QQuickWidget` is the whole host — no `QDialog`, no `Overlay` chrome.

What carries over from both those hosts, because the underlying Qt gotchas
are the same regardless of modality: `ensure_qml_style()` before the source
loads (native style silently drops `background:`), a transparent clear
colour so the surrounding QtWidgets card shows through instead of an opaque
white rectangle, and load-or-raise instead of `QQuickWidget`'s own
fail-silent-and-render-a-blank-box behaviour — `qml-rule.md` §7 requires
every host to do this, not just the two that came first.

@par Why a component-specific class instead of a generic "inline QML" host
`ProgressBanner.qml` is the only kit component embedded inline so far —
one caller, one shape. A generic `QmlInlineWidget(qml_file, context)` base
would be the kind of "abstraction with nothing to derive" `qml-rule.md`
§1.3 and `architecture-rule.md` §7.2 both warn against: there is no second
inline embed yet to prove out what such a base should generalise over. If
`StatCard`/`StatusPill`/`LogPanel` grow inline hosts later, that is the
time to look at what they have in common and factor it out — not before.

@par What this class owns vs. what stays in the screen
Per `qml-rule.md` §1.3 the caller does no dictionary building or type
coercion; it does no per-tick math either, since
`DataManagementViewModel.progressPercent` already computes and clamps that
number (`data_management_view_model.py`) — this class is only the five
plain setters `_sync_progress()` already called on `AppProgressBar` (plus
one new one, `set_percent`, replacing the old `set_range`/`set_value`
pair), and the one signal a Cancel click needs to reach the ViewModel.
`ProgressBanner.qml`'s own Cancel `Button` replaces `AppProgressBar`'s
sibling `QPushButton` entirely — this host does not construct a second one.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import StyleRole

from ..embed import QuickSurface

_QML_FILE = Path(__file__).with_name("ProgressBanner.qml")


class ProgressBannerWidget(QuickSurface):
    """@brief Inline (non-modal) host for `ProgressBanner.qml`.

    @details Plain setters, not Qt `Property`/`Signal` reflection into QML —
    there is no widget ViewModel here to expose them on (`qml-rule.md`
    §1.3), so the screen's own `_sync_progress()` calls these directly, the
    same call shape it used against `AppProgressBar`.
    """

    #: Re-exported from the QML root's own `cancelRequested()` so callers
    #: never need to reach into `root_object` for it.
    cancelRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        # Every caller places this banner on a SURFACE-coloured card
        # (`backtest_top_panel.py`'s BG_CARD frame, Data Management's and Dev
        # Board's panels); `QuickSurface` clears to that token (BUG-115).
        super().__init__(
            _QML_FILE,
            surface=StyleRole.SURFACE,
            object_name="progressBannerQuick",
            parent=parent,
        )
        self.setObjectName("progressBannerWidget")
        self._root = self.root_object
        self._root.cancelRequested.connect(self.cancelRequested)

    def set_status_text(self, text: str) -> None:
        self._root.setProperty("statusText", text)

    def set_percent(self, value: float) -> None:
        """@param value 0..100. Ignored by the QML side while indeterminate."""
        self._root.setProperty("percent", value)

    def set_indeterminate(self, indeterminate: bool) -> None:
        self._root.setProperty("indeterminate", indeterminate)

    def set_cancelling(self, cancelling: bool) -> None:
        self._root.setProperty("cancelling", cancelling)

    def set_cancel_label(self, text: str) -> None:
        self._root.setProperty("cancelLabel", text)
