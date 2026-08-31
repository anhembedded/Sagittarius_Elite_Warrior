"""`PageShell` — the four-band page scaffold every screen in the App tab is
built from: header, optional context bar, workspace (with an optional
right-hand rail), optional console.

@details
Before this existed, each screen (`DashboardView`, `BackTestView`,
`DataManagementView`, `SettingsView`) built its own top-level `QVBoxLayout`
by hand, and the shapes drifted independently: Dev Board's title sat buried
inside its right rail instead of a page-level header, Backtest had no
header band at all (its "Run" button lived inside the toolbar row), and
Database put its secondary controls in a rail on the **left** — the one
placement the design explicitly rules out ("rail is always on the right,
never the left").

This is a pure layout composite, not a `Surface`/`Card`: it paints no
background and draws no border of its own (`# base-exempt` below, same
call `DevBoardPanel`/`BackTestTopPanel` already make) — it only arranges
whatever the caller hands it. Every screen keeps 100% of its existing
widgets and behaviour; only which container they sit inside changes.

A band with nothing to show is not left as empty space — `set_context_bar`
and `set_console` fully hide their band when passed `None`, so a screen
that has no console (Settings) does not carry a blank strip an
Indicators-panel-shaped complaint would call "hiển thị thiếu" for the
wrong reason.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..assets import Palette

#: `QSplitter`'s initial pane split, not a hard cap — the user can still
#: drag the handle. Matches the Pattern Library's "300px rail" as a
#: starting point, not a `setFixedWidth` (the exact "fix size nhiều quá"
#: complaint this session's other fix already addressed once).
_RAIL_INITIAL_WIDTH = 300


class PageShell(QWidget):  # base-exempt: pure layout composite, no chrome of its own
    """Compose into this — do not subclass it. A screen's `View` builds its
    own content widgets exactly as before, then hands them to
    `set_header`/`set_context_bar`/`set_workspace`/`set_console` in whatever
    order it likes; each setter can be called again later to replace a
    band's content."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(12)

        outer.addWidget(self._build_header_row())

        self._context_bar_container, self._context_bar_layout = (
            self._build_slot_container()
        )
        outer.addWidget(self._context_bar_container)

        self._workspace_container, workspace_layout = self._build_slot_container()
        outer.addWidget(self._workspace_container, 1)
        # Built once and kept for the shell's whole lifetime — never
        # replaced by `set_workspace()`. A splitter recreated on every call
        # would, once discarded, take its *current* children down with it
        # (an unparented `QSplitter` with no Python reference left is
        # garbage-collected immediately, and Qt cascades that deletion to
        # its own children) — destroying `main`/`rail` widgets the caller
        # fully expects to keep reusing (e.g. `DashboardView.scroll_area`
        # survives from `_setup_ui()` into a later `set_view_model()` call).
        self._workspace_splitter = QSplitter()
        workspace_layout.addWidget(self._workspace_splitter)

        self._console_container, self._console_layout = self._build_slot_container()
        outer.addWidget(self._console_container)

        self._context_bar_container.setVisible(False)
        self._console_container.setVisible(False)

    @staticmethod
    def _build_slot_container() -> tuple[QWidget, QVBoxLayout]:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        return container, layout

    # ------------------------------------------------------------------ #
    # Header — always present; every screen has a name.
    # ------------------------------------------------------------------ #

    def _build_header_row(self) -> QWidget:
        header = QWidget()
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self._header_icon_label = QLabel()
        self._header_icon_label.hide()
        row.addWidget(self._header_icon_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        self._title_label = QLabel()
        self._title_label.setObjectName("pageShellTitle")
        self._title_label.setStyleSheet(
            f"color: {Palette.ACCENT}; font-size: 15px; font-weight: bold;"
        )
        self._subtitle_label = QLabel()
        self._subtitle_label.setObjectName("pageShellSubtitle")
        self._subtitle_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 11px;")
        self._subtitle_label.hide()
        title_box.addWidget(self._title_label)
        title_box.addWidget(self._subtitle_label)
        row.addLayout(title_box)

        row.addStretch(1)

        self._header_actions_row = QHBoxLayout()
        self._header_actions_row.setSpacing(8)
        row.addLayout(self._header_actions_row)

        return header

    def set_header(
        self,
        title: str,
        subtitle: str = "",
        *,
        icon: QIcon | None = None,
        actions: QWidget | Sequence[QWidget] | None = None,
    ) -> None:
        """@param icon Already built by the caller (icon size is a
        per-screen call, not this shell's concern) — passed through to
        `QLabel.setPixmap` via `QIcon.pixmap`.
        @param actions One widget, several, or none — every screen so far
        wants 0-2 buttons here (Database's Vacuum/Purge, Settings' Save,
        Backtest's Run), so no scroll/overflow handling is needed yet.
        """
        self._title_label.setText(title)
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))

        if icon is not None:
            self._header_icon_label.setPixmap(icon.pixmap(22, 22))
            self._header_icon_label.show()
        else:
            self._header_icon_label.hide()

        self._clear_layout(self._header_actions_row)

        for widget in self._as_widget_list(actions):
            self._header_actions_row.addWidget(widget)

    # ------------------------------------------------------------------ #
    # Context bar — optional. "which data you're looking at": symbol,
    # timeframe, range, timezone. Fully collapses when unset.
    # ------------------------------------------------------------------ #

    def set_context_bar(self, widget: QWidget | None) -> None:
        self._replace_slot_content(
            self._context_bar_container, self._context_bar_layout, widget
        )

    # ------------------------------------------------------------------ #
    # Workspace — always present: `main` plus an optional right-hand rail.
    # The rail can only ever land on the right — there is no parameter
    # that places it anywhere else.
    # ------------------------------------------------------------------ #

    def set_workspace(self, main: QWidget, rail: QWidget | None = None) -> None:
        splitter = self._workspace_splitter
        while splitter.count():
            # Detaches the pane, it does not destroy it: `setParent(None)`
            # on the real widget the caller passed in (not a disposable
            # wrapper), which the caller's own Python reference keeps alive.
            pane = splitter.widget(0)
            if pane is not None:
                pane.setParent(None)

        splitter.addWidget(main)
        if rail is not None:
            splitter.addWidget(rail)
            main_width = max(self.width() - _RAIL_INITIAL_WIDTH, _RAIL_INITIAL_WIDTH)
            splitter.setSizes([main_width, _RAIL_INITIAL_WIDTH])

    # ------------------------------------------------------------------ #
    # Console — optional. The log/append component, same shape (usually
    # `AppLogPanel`) on every screen that has one. Fully collapses when
    # unset, same as the context bar.
    # ------------------------------------------------------------------ #

    def set_console(self, widget: QWidget | None) -> None:
        self._replace_slot_content(
            self._console_container, self._console_layout, widget
        )

    # ------------------------------------------------------------------ #
    # Shared plumbing
    # ------------------------------------------------------------------ #

    @classmethod
    def _replace_slot_content(
        cls, container: QWidget, layout: QLayout, widget: QWidget | None
    ) -> None:
        cls._clear_layout(layout)
        if widget is not None:
            layout.addWidget(widget)
        container.setVisible(widget is not None)

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            child = item.widget() if item is not None else None
            if child is not None:
                child.setParent(None)

    @staticmethod
    def _as_widget_list(actions: QWidget | Sequence[QWidget] | None) -> list[QWidget]:
        if actions is None:
            return []
        if isinstance(actions, QWidget):
            return [actions]
        return list(actions)
