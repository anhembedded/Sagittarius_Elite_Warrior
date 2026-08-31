"""
@brief The showcase window itself, and the introspection the coverage guard
reads.
"""

from __future__ import annotations

import sys
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Badge,
    Banner,
    Card,
    Column,
    ConfirmOverlay,
    DataRow,
    DateRangeOverlay,
    DateTimeField,
    LogPanel,
    PageShell,
    Pagination,
    Panel,
    PickerItem,
    PickerOverlay,
    RangePreset,
    RowAction,
    SectionLabel,
    SelectableCard,
    Severity,
    StyledButton,
    StyledCheckBox,
    StyledField,
    StyledProgressBar,
    StyleRole,
    Tab,
    TabBar,
    TableCard,
    Tone,
    semantic_colour,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit.overlays import (
    DEFAULT_PRESETS,
)
from sagittarius_engine.extensions.pyside_mvc.tokens import get_theme_bridge

#: A neutral palette so the gallery renders standalone. Not any consuming
#: app's identity — the point is to see the *shapes* and how the roles
#: differentiate them, which a real brand palette would only distract from.
_SHOWCASE_PALETTE: dict[str, str] = {
    "bg": "#101216",
    "bgSidebar": "#0c0e12",
    "bgCard": "#171a21",
    "bgCardHeader": "#1e222b",
    "border": "#2b303b",
    "textPrimary": "#e7e9ee",
    "accent": "#5aa9e6",
    "success": "#3ecf8e",
    "warning": "#e0a23c",
    "danger": "#ef5f6b",
    "muted": "#8a93a3",
}

_COLUMNS = (
    Column("Name", 30),
    Column("Status", 20, Qt.AlignmentFlag.AlignCenter),
    Column("Total", 16, Qt.AlignmentFlag.AlignRight),
)


class ShowcaseWindow(QWidget):  # base-exempt: the gallery shell, not a surface
    """
    @brief One scrolling column, one section per widget type.

    @details Builds every section eagerly rather than lazily per tab: the
    guard asks which types were actually constructed, and a lazy gallery
    could pass it while rendering nothing.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("presentation.ui.kit — showcase")
        self.resize(760, 900)
        # The gallery shell paints the app background itself. Without this
        # it inherits Qt's light grey default, and every widget here is
        # designed for a dark ground — muted text on light grey is
        # unreadable, which made the first screenshot of this window a
        # worse advert for the kit than no screenshot at all.
        # `semantic_colour` rather than a literal: this is the same `bg`
        # token a real app would supply.
        self._ground = (
            f"background-color: {semantic_colour('bg')};"
            f"color: {semantic_colour('textPrimary')};"
        )
        self.setStyleSheet(f"ShowcaseWindow {{{self._ground}}}")

        #: Every type this window put on screen. Read by the coverage guard.
        self.built: list[type] = []

        column = QVBoxLayout()
        for build in (
            self._surfaces,
            self._controls,
            self._labels,
            self._data,
            self._banners,
            self._overlays,
            self._page_shell,
        ):
            build(column)
        column.addStretch(1)

        host = QWidget()
        host.setLayout(column)
        # The scroll area's viewport is its own widget and does not
        # inherit the shell's rule, so it is painted explicitly rather
        # than by a wider selector that would also repaint every child
        # label sitting on a card.
        host.setStyleSheet(f"QWidget {{{self._ground}}}")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)

        outer = QVBoxLayout(self)
        outer.addWidget(scroll)

    def _add(self, column: QVBoxLayout, heading: str, *widgets: QWidget) -> None:
        column.addWidget(SectionLabel(heading, tick=True))
        row = QHBoxLayout()
        for widget in widgets:
            self.built.append(type(widget))
            row.addWidget(widget)
        row.addStretch(1)
        column.addLayout(row)

    def _surfaces(self, column: QVBoxLayout) -> None:
        card = Card("Card")
        panel = Panel()
        selectable = SelectableCard()
        selectable.selected = True
        self._add(column, "Surfaces", card, panel, selectable)

    def _controls(self, column: QVBoxLayout) -> None:
        progress = StyledProgressBar()
        progress.setValue(64)
        progress.setTextVisible(True)
        self._add(
            column,
            "Controls",
            StyledButton("Primary", role=StyleRole.PRIMARY_BUTTON),
            StyledButton("Secondary"),
            StyledButton("Danger", role=StyleRole.DANGER_BUTTON),
            StyledCheckBox("Checkbox"),
            StyledField(),
            DateTimeField(),
            progress,
        )

    def _labels(self, column: QVBoxLayout) -> None:
        self._add(
            column,
            "Labels and badges",
            SectionLabel("Section label"),
            SectionLabel("With tick", tick=True),
            Badge("12"),
            Badge("current", emphasised=True),
            Badge("+4.20%", tone=Tone.POSITIVE),
            Badge("-1.80%", tone=Tone.NEGATIVE),
        )

    def _data(self, column: QVBoxLayout) -> None:
        row = DataRow(_COLUMNS, actions=[RowAction("Open")])
        row.set_cells(["Alpha", "healthy", "1 204"])

        table = TableCard(
            "Table card", _COLUMNS, pagination=Pagination.FULL, empty_text="Nothing yet"
        )
        second = DataRow(_COLUMNS)
        second.set_cells(["Beta", "stale", "97"])
        table.set_rows([second])
        table.set_page(2, 7)
        table.set_count_text("Showing 21–40 of 137")

        tabs = TabBar([Tab("a", "First", "12"), Tab("b", "Second", "340")])

        log = LogPanel("Log panel")

        self._add(column, "Data shapes", row)
        self._add(column, "Table, tabs and log", table, tabs, log)

    def _banners(self, column: QVBoxLayout) -> None:
        self._add(
            column,
            "Banners",
            Banner("An informational notice", icon="i", severity=Severity.INFO),
            Banner(
                "Results are stale",
                icon="!",
                severity=Severity.WARN,
                action_text="Re-run",
            ),
            Banner("Something failed", icon="x", severity=Severity.DANGER),
        )

    def _overlays(self, column: QVBoxLayout) -> None:
        """Overlays are modal dialogs, so they are built and shown inline
        rather than opened — the guard needs them constructed, and a gallery
        that blocked on a modal could never render the rest of itself."""
        confirm = ConfirmOverlay(
            "Confirm overlay", "subtitle", message="This cannot be undone.", danger=True
        )
        picker = PickerOverlay("Picker overlay", searchable=True)
        picker.set_items(
            [
                PickerItem("a", "First choice", "with a subtitle"),
                PickerItem("b", "Second"),
            ]
        )
        # A fixed pair rather than `date.today()`: the showcase doubles as
        # the visual baseline, and a gallery whose calendar moves every day
        # cannot be compared against yesterday's capture.
        date_range = DateRangeOverlay(
            "Date range overlay",
            start=date(2026, 8, 19),
            end=date(2026, 8, 26),
            presets=(*DEFAULT_PRESETS, RangePreset("All history")),
        )
        date_range.summary = "7 days · 2026-08-19 → 2026-08-26"
        for overlay in (confirm, picker, date_range):
            overlay.setParent(self)
            overlay.setWindowFlags(Qt.WindowType.Widget)
            overlay.setModal(False)
        self._add(column, "Overlays", confirm, picker, date_range)

    def _page_shell(self, column: QVBoxLayout) -> None:
        shell = PageShell()
        shell.setMinimumSize(420, 260)
        shell.set_header(
            "Page shell",
            "Header + optional context bar + workspace/rail + optional console",
            actions=StyledButton("Action"),
        )
        shell.set_context_bar(SectionLabel("Context bar"))
        shell.set_workspace(Panel(), rail=Panel())
        shell.set_console(LogPanel("Console"))
        self._add(column, "Page shell", shell)


def showcased_types() -> set[str]:
    """
    @brief The names of every widget type the showcase actually constructs.

    @details Built by constructing the window, not by reading its source —
    a gallery that imports a type without ever putting it on screen would
    pass a source scan and prove nothing. Requires a `QApplication`; the
    coverage guard supplies one via `qtbot`.
    """
    get_theme_bridge(_SHOWCASE_PALETTE)
    window = ShowcaseWindow()
    return {cls.__name__ for cls in window.built}


def main() -> int:
    app = QApplication(sys.argv)
    get_theme_bridge(_SHOWCASE_PALETTE)
    window = ShowcaseWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover — the runnable entry point
    raise SystemExit(main())
