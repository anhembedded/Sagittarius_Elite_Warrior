"""Embeds `StatCardRow.qml` inline in `BackTestTopPanel`'s own layout — the
dynamic row of primary performance stat cards
(`BackTestViewModel.primaryStatCards`), replacing per-run construction/
teardown of the QtWidgets `StatCard` (`kit/surfaces/stat_card.py`).

@par Why a bare `QQuickWidget`, not `QmlOverlay`
Same reasoning `qml/kit/progress_banner_widget.py` documents for its own
host: this row is not a dialog, it sits inside `BackTestTopPanel`'s own
`QVBoxLayout` in the exact spot the old `QHBoxLayout` of `StatCard` widgets
occupied — `qml-rule.md` §0's two "Modal QML" host shapes both assume a
`QDialog`, which nothing here needs.

@par Why this needs a widget VM, unlike `ProgressBannerWidget`
`ProgressBannerWidget` has no VM because every value it sets is already the
exact value the screen ViewModel computed. This host cannot make the same
claim: `BackTestViewModel.primaryStatCards` carries raw `Tone` enum members
(`valueTone`/`badgeTone`), and QML reads plain data, not a Python `Enum` —
see `stat_card_row_vm.py` for the one conversion this widget needs.

@par Why callback-constructed
Same pattern `qml-rule.md` §1.1 documents for every widget ViewModel in
this rollout (`SelectListVM(get_options=..., ...)`) — the constructor takes
a `get_cards` callback rather than a `BackTestViewModel` reference, so this
widget stays testable and reusable without importing anything from
`screens/backtest/` (`qml/` must not depend on `screens/` — the reverse
dependency `backtest_top_panel.py` already has is the one direction this
rollout uses throughout).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

from ..style import ensure_qml_style
from .stat_card_row_vm import StatCardRowVM

_QML_FILE = Path(__file__).with_name("StatCardRow.qml")


class StatCardRowWidget(QQuickWidget):
    """@brief Inline (non-modal) host for `StatCardRow.qml`.

    @details `refresh()` re-pulls `get_cards()` and re-converts every card
    into QML-ready data (`StatCardRowVM.refresh()`). Callers decide *when*
    to call it (`BackTestTopPanel._sync_stat_cards()` calls it once per
    `statCardsChanged` emission) — this class does not also subscribe to
    anything on its own, so there is exactly one place that decides the
    refresh cadence.
    """

    def __init__(
        self,
        get_cards: Callable[[], Sequence[Mapping[str, object]]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statCardRowWidget")
        ensure_qml_style()
        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        # Transparent so the QtWidgets card (`StyleRole.SURFACE`) behind
        # `BackTestTopPanel`'s own layout shows through — same reasoning as
        # every other inline host in this rollout
        # (`ProgressBannerWidget`/`DatabaseStatusPanel`).
        self.setClearColor(Qt.GlobalColor.transparent)

        self._vm = StatCardRowVM(get_cards, parent=self)

        # A QML context property is a borrowed pointer; held on `self` so
        # `Theme` stays alive for as long as this scene can read it (same
        # note as `ProgressBannerWidget`/`DatabaseStatusPanel`).
        self._theme = get_theme_bridge()
        root_context = self.rootContext()
        root_context.setContextProperty("vm", self._vm)
        root_context.setContextProperty("Theme", self._theme)

        self.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
        if self.status() is not QQuickWidget.Status.Ready:
            raise RuntimeError(
                f"QML failed to load: {_QML_FILE}\n"
                + "\n".join(error.toString() for error in self.errors())
            )

        root = self.rootObject()
        if root is None:  # pragma: no cover - status check above already raises
            raise RuntimeError("StatCardRow QML root object is missing")
        self._root = root
        self.refresh()

    @property
    def root_object(self) -> QObject:
        """The loaded QML root, for tests to reach in by `objectName`."""
        return self._root

    def refresh(self) -> None:
        """Re-pulls `get_cards()` and rebuilds every `StatCard` delegate.

        `qml-rule.md` §4.2: a `Repeater` over a list-of-dicts model
        destroys and recreates every delegate on any change — see
        `NOTES.md` for how often this actually fires during a live
        Backtest run (an event, not a per-tick rebuild)."""
        self._vm.refresh()
