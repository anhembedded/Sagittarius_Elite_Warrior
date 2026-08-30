"""`StatusPillWidget` — a bare `QQuickWidget` embedding `StatusPill.qml` inline.

@par Why not `QmlOverlay` or `SymbolPickerModal`
`qml-rule.md` §0.1 names two *modal* QML shapes, both hosted by a real
`QDialog` because a `Popup`'s dim/block only reaches the `Window` it lives
in. Neither applies here: this widget is not modal at all — it sits inside
`DevBoardPanel`'s own header row, in the exact spot the bare `QLabel` +
colour-square `QFrame` WS badge used to occupy (`EPIC-015` Phase 4, the
rollout's first QML panel embedded directly beside the live pyqtgraph
chart — see `qml-rule.md` §0's "Panel QML cạnh chart" row and the epic's
own §6 stop condition). There is nothing to dim or block, so a plain
`QQuickWidget` is the whole host — no `QDialog`, no `Overlay` chrome. This
is the same shape `progress_banner_widget.py`'s `ProgressBannerWidget`
already proved out for Data Management's inline `ProgressBanner.qml`
embed; this class mirrors it property-for-property.

What carries over from every prior host, because the underlying Qt
gotchas are the same regardless of modality: `ensure_qml_style()` before
the source loads (native style silently drops `background:`), a
transparent clear colour so the surrounding QtWidgets chrome shows
through instead of an opaque white rectangle, and load-or-raise instead
of `QQuickWidget`'s own fail-silent-and-render-a-blank-box behaviour —
`qml-rule.md` §7 requires every host to do this, not just the ones that
came first.

@par Why a component-specific class instead of a generic "inline QML" host
`progress_banner_widget.py`'s own docstring already declined to build a
generic `QmlInlineWidget(qml_file, context)` base after its first inline
embed — one caller was not enough evidence for what such a base should
generalise over. A second inline embed with an *identical* shape (no
context property beyond `Theme`, plain setters, load-or-raise) is still
not the same as "this widget's needs differ from `ProgressBannerWidget`'s
in a way worth abstracting over" — `StatusPill.qml` has no signal to
re-export (unlike `ProgressBanner.qml`'s `cancelRequested`), which is the
one thing that would have made a shared base need a hook at all. Revisit
if a third inline `kit/` embed appears and the three together show a real
common shape.

@par What this class owns vs. what stays in the screen
Per `qml-rule.md` §1.3 `StatusPill.qml` is pure presentational (text/tone/
showDot, no business logic) — this class is only the two plain setters
`DevBoardPanel._sync_ws_status()` already needs (`set_text`, `set_tone`),
matching the existing call shape it used against the `QLabel`/`QFrame`
pair. There is no widget ViewModel here: deriving "idle"/"active"/
"success"/"danger" from `UIMode` is a screen-level concern
(`dashboard_presenter.py`'s `_WS_STATUS_BY_MODE`), not something this
component needs to know how to do.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

from ..style import ensure_qml_style

_QML_FILE = Path(__file__).with_name("StatusPill.qml")


class StatusPillWidget(QQuickWidget):
    """@brief Inline (non-modal) host for `StatusPill.qml`.

    @details Plain setters, not Qt `Property`/`Signal` reflection into
    QML — there is no widget ViewModel here to expose them on
    (`qml-rule.md` §1.3), so the screen's own `_sync_ws_status()` calls
    these directly, the same call shape it used against the old
    `QLabel`/`QFrame` pair.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusPillWidget")
        ensure_qml_style()
        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        # Transparent so the QtWidgets header row behind this widget shows
        # through — same reasoning as `ProgressBannerWidget`/`QmlOverlay`.
        self.setClearColor(Qt.GlobalColor.transparent)

        # A QML context property is a borrowed pointer; held on `self` so
        # `Theme` stays alive for as long as this scene can read it (same
        # note as every other host).
        self._theme = get_theme_bridge()
        self.rootContext().setContextProperty("Theme", self._theme)

        self.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
        if self.status() is not QQuickWidget.Status.Ready:
            raise RuntimeError(
                f"QML failed to load: {_QML_FILE}\n"
                + "\n".join(error.toString() for error in self.errors())
            )

        root = self.rootObject()
        if root is None:  # pragma: no cover - status check above already raises
            raise RuntimeError("StatusPill QML root object is missing")
        self._root = root

    @property
    def root_object(self) -> QObject:
        """The loaded QML root, for tests to reach in by `objectName`."""
        return self._root

    def set_text(self, text: str) -> None:
        self._root.setProperty("text", text)

    def set_tone(self, tone: str) -> None:
        """@param tone One of "idle" | "active" | "success" | "danger" —
        see `StatusPill.qml`'s own docstring for the vocabulary."""
        self._root.setProperty("tone", tone)

    def set_show_dot(self, show_dot: bool) -> None:
        self._root.setProperty("showDot", show_dot)
