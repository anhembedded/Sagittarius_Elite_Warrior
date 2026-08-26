"""The gap inspector, its row widget, and its coverage-bar segment.

`_CoverageSegmentWidget` stays under `screens/` on purpose: `EPIC-007F`
requirement 5 records it as Data Management's own domain concept -- a
data-coverage bar over a time range -- not a shape for the kit."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Column,
    DataRow,
    Overlay,
    RowAction,
    StyleRole,
    Tone,
    apply_role,
)

if TYPE_CHECKING:
    from ..data_management_view_model import DataManagementViewModel


_FULL_COVERAGE_THRESHOLD = 99.0

_GAP_COLUMNS = (
    Column("#", 6),
    Column("START (FROM)", 25),
    Column("END (TO)", 25),
    Column("DURATION", 12),
    Column("MISSING", 14),
)

_GAP_ACTION_COLUMN = Column("ACTION", 18)

_GAP_ID_CELL, _GAP_START_CELL, _GAP_END_CELL, _GAP_DURATION_CELL, _GAP_MISSING_CELL = (
    range(len(_GAP_COLUMNS))
)

_REPAIR_ACTION = 0


class _GapRowWidget(DataRow):
    """One row of the gap table, on the engine's `DataRow`.

    `gapList` is a plain `QVariantList` (`list[dict]`), not a Qt model, so
    these rows are built from Python data directly rather than through
    `setIndexWidget` — which is why the dialog owning them rebuilds the
    whole list on every refresh.
    """

    def __init__(
        self,
        index: int,
        gap: dict,
        on_repair: Callable[[dict], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            _GAP_COLUMNS,
            actions=[RowAction("Vá Gap")],
            action_stretch=_GAP_ACTION_COLUMN.stretch,
            parent=parent,
        )
        self.setFixedHeight(36)
        self.layout().setContentsMargins(8, 0, 8, 0)
        self.layout().setSpacing(6)

        # Zebra striping, scoped to this class so it cannot cascade into the
        # cells — an unscoped property list is Qt's universal selector and
        # overrides a child's own colour (`BUG-008`).
        if index % 2:
            self.setStyleSheet(
                f"{type(self).__name__} {{ background-color: "
                f"{Palette.BG_CARD_HEADER}; border-radius: 4px; }}"
            )

        self.set_cell_role(_GAP_ID_CELL, StyleRole.CAPTION)
        self.set_cell_role(_GAP_DURATION_CELL, StyleRole.TABLE_CELL_STRONG)
        # Accent marks the duration as the notable field — not a `Tone`,
        # because "notable" is not a judgement about the value.
        self.set_cell_colour(_GAP_DURATION_CELL, "accent")
        self.set_cell_role(_GAP_MISSING_CELL, StyleRole.TABLE_CELL_STRONG)
        self.set_cell_tone(_GAP_MISSING_CELL, Tone.NEGATIVE)

        self.set_cells(
            [
                str(gap.get("gap_id") or (index + 1)),
                str(gap.get("start_time") or ""),
                str(gap.get("end_time") or ""),
                str(gap.get("duration_text") or ""),
                f"-{gap.get('missing_candles') or 0} nến",
            ]
        )

        repair_button = self.action_buttons[_REPAIR_ACTION]
        repair_button.setObjectName(f"btnRepairGap_{index}")
        repair_button.setFixedHeight(24)
        self.action_triggered.connect(lambda _position: on_repair(gap))

    def set_enabled(self, enabled: bool) -> None:
        self.action_buttons[_REPAIR_ACTION].setEnabled(enabled)


class _CoverageSegmentWidget(QFrame):  # base-exempt: a coloured bar segment
    """One segment of the timeline coverage bar — port of the QML `Repeater`
    inside the coverage `Rectangle`. Width is proportional to `ratio` within
    its host's `resizeEvent`-driven layout (a plain `QHBoxLayout` with
    stretch factors does the same job as QML's `width: parent.width * ratio`,
    since Qt layouts already distribute width by relative stretch).

    **Deviates from `EPIC-007F` requirement 5, which said to inherit
    `Panel`.** That instruction predates two things learned during the
    task: `Panel` applies `SURFACE`, so this segment would inherit a card
    background, a border and a radius — every one of which it then has to
    override, because it is a flat translucent block of one domain colour.
    Inheriting a base only to undo all of it is worse than saying plainly
    that this is not a surface. Recorded rather than done silently."""

    def __init__(self, segment: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        is_gap = bool(segment.get("is_gap"))
        color = Palette.DANGER if is_gap else Palette.SUCCESS
        opacity = "e6" if is_gap else "bf"  # ~0.9 / ~0.75 alpha, matches QML
        self.setStyleSheet(f"background-color: {color}{opacity};")
        tip = (
            f"{'⚠️ GAP: ' if is_gap else '✅ DATA: '}"
            f"{segment.get('start_time', '')} → {segment.get('end_time', '')} "
            f"({segment.get('candle_count', 0)} nến)"
        )
        self.setToolTip(tip)


class GapInspectorDialog(Overlay):
    """Port of `GapInspectorModal.qml`: timeline coverage bar, a gaps table
    (plain Python list rows, no Qt model — `gapList`/`coverageSegments` are
    `QVariantList` properties, rebuilt wholesale on change same as the QML
    `Repeater` did), and footer Repair-All/Close actions. Stays alive for the
    view's lifetime, same as `KLineInspectorDialog`.

    Its Repair-All/Close row is `Overlay`'s footer, supplied through
    `_build_buttons()`. That runs from `Overlay.__init__`, before this
    class's own body — which is fine here because nothing it builds reads
    `_view_model` until a button is actually pressed.
    """

    def __init__(
        self, view_model: DataManagementViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHI TIẾT LỖ HỔNG DỮ LIỆU (GAP INSPECTOR)", parent=parent)
        self.setObjectName("gapInspectorModal")
        self._view_model = view_model
        self.resize(680, 520)
        apply_role(self.title_label, StyleRole.HEADING)
        self._subtitle_label.setVisible(True)

        outer = self.body_layout
        outer.setSpacing(12)

        outer.addLayout(self._build_coverage_bar())
        outer.addWidget(self._build_column_header())
        outer.addWidget(self._build_table(), 1)

        view_model.gapInspectorChanged.connect(self._sync_header)
        view_model.gapListChanged.connect(self._rebuild_rows)
        view_model.coverageSegmentsChanged.connect(self._rebuild_coverage_bar)
        view_model.uiModeChanged.connect(self._sync_enabled_state)

        self._sync_header()
        self._rebuild_rows()
        self._rebuild_coverage_bar()

    def _build_coverage_bar(self) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(4)

        header = QHBoxLayout()
        label = QLabel("TIMELINE COVERAGE")
        label.setStyleSheet(
            f"color: {Palette.MUTED}; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        )
        header.addWidget(label)
        header.addStretch()
        self._coverage_pct_label = QLabel()
        header.addWidget(self._coverage_pct_label)
        box.addLayout(header)

        self._coverage_bar_frame = QFrame()
        self._coverage_bar_frame.setFixedHeight(18)
        # Scoped by hand rather than given `SURFACE`: this is an 18px-tall
        # meter whose children are the coloured coverage segments, and
        # `SURFACE`'s 8px radius would round a bar half that height.
        self._coverage_bar_frame.setStyleSheet(
            f"QFrame {{ background-color: {Palette.BG_CARD}; "
            f"border: 1px solid {Palette.BORDER}; border-radius: 4px; }}"
        )
        self._coverage_bar_layout = QHBoxLayout(self._coverage_bar_frame)
        self._coverage_bar_layout.setContentsMargins(1, 1, 1, 1)
        self._coverage_bar_layout.setSpacing(0)
        box.addWidget(self._coverage_bar_frame)

        return box

    def _build_column_header(self) -> QFrame:
        header = QFrame()
        header.setFixedHeight(28)
        apply_role(header, StyleRole.TABLE_HEADER)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)
        for spec in (*_GAP_COLUMNS, _GAP_ACTION_COLUMN):
            label = QLabel(spec.label)
            apply_role(label, StyleRole.SECTION_LABEL)
            layout.addWidget(label, spec.stretch)
        return header

    def _build_table(self) -> QWidget:
        host = QWidget()
        host.setObjectName("gapListView")
        self._rows_layout = QVBoxLayout(host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(2)

        self._empty_label = QLabel(
            "Không có lỗ hổng nào được phát hiện (Dữ liệu liên tục 100%)."
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {Palette.SUCCESS}; font-size: 12px; font-weight: bold;"
        )
        self._rows_layout.addWidget(self._empty_label)
        self._rows_layout.addStretch(1)

        # The rows host paints the card colour itself. It used to inherit it
        # from the dialog's own unscoped stylesheet — which is to say from
        # `BUG-008` — and lost it the moment the dialog moved onto `Overlay`
        # and got a properly scoped one, leaving a white panel behind the
        # rows. Scoped by `objectName` so it reaches this widget only.
        host.setStyleSheet(f"#gapListView {{ background-color: {Palette.BG_CARD}; }}")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Scoped: unscoped, `border: none` would strip the border from every
        # descendant that does not set one of its own (`BUG-008`), and this
        # scroll area contains the whole gap-row list. The viewport is a
        # child widget of its own, so it needs naming separately — the
        # scroll area's own rule does not reach it.
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background-color: {Palette.BG_CARD}; }}"
        )
        scroll.setWidget(host)
        self._row_widgets: list[_GapRowWidget] = []
        return scroll

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        self._total_missing_label = QLabel()
        self._total_missing_label.setStyleSheet(
            f"color: {Palette.DANGER}; font-size: 11px; font-weight: bold;"
        )
        row.addWidget(self._total_missing_label)
        row.addStretch()

        self._btn_repair_all = QPushButton("Vá Toàn Bộ Lỗ Hổng (Repair All)")
        self._btn_repair_all.setObjectName("btnRepairAllGaps")
        self._btn_repair_all.setIcon(
            get_icon_loader().get_icon("zap", Palette.ACCENT, 14)
        )
        self._btn_repair_all.setFixedHeight(32)
        self._btn_repair_all.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.BG_CARD_HEADER}; color: {Palette.ACCENT}; "
            f"border: 1px solid {Palette.ACCENT}; border-radius: 6px; font-size: 11px; "
            f"font-weight: bold; padding: 0 10px; }} "
            f"QPushButton:hover {{ background-color: {Palette.STATE_HOVER_BG}; }} "
            f"QPushButton:disabled {{ color: {Palette.MUTED}; border-color: {Palette.BORDER}; }}"
        )
        self._btn_repair_all.clicked.connect(self._on_repair_all)
        row.addWidget(self._btn_repair_all)

        btn_close = QPushButton("Đóng")
        btn_close.setFixedSize(80, 32)
        btn_close.setStyleSheet(
            f"QPushButton {{ background-color: {Palette.BG_CARD}; color: {Palette.TEXT_PRIMARY}; "
            f"border: 1px solid {Palette.BORDER}; border-radius: 6px; }}"
        )
        btn_close.clicked.connect(self.close)
        row.addWidget(btn_close)

        return row

    def _on_repair(self, gap: dict) -> None:
        vm = self._view_model
        start = gap.get("fetch_start_time") or gap.get("start_time")
        end = gap.get("fetch_end_time") or gap.get("end_time")
        vm.requestRepairGap(vm.gapInspectorSymbol, vm.gapInspectorInterval, start, end)

    def _on_repair_all(self) -> None:
        vm = self._view_model
        vm.requestRepairAllGaps(vm.gapInspectorSymbol, vm.gapInspectorInterval)

    def _sync_header(self) -> None:
        vm = self._view_model
        self._subtitle_label.setText(
            f"{vm.gapInspectorSymbol} ({vm.gapInspectorInterval}) • "
            f"{vm.gapInspectorTotalGaps} gaps detected"
        )
        coverage_pct = vm.gapInspectorCoveragePct
        self._coverage_pct_label.setText(f"Độ phủ: {coverage_pct}%")
        color = (
            Palette.SUCCESS
            if coverage_pct >= _FULL_COVERAGE_THRESHOLD
            else Palette.ACCENT
        )
        self._coverage_pct_label.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold;"
        )
        self._total_missing_label.setText(
            f"Tổng số nến bị thiếu: {vm.gapInspectorTotalMissing} nến"
        )
        self._sync_enabled_state()

    def _sync_enabled_state(self) -> None:
        idle = self._view_model.uiMode == "IDLE"
        has_gaps = len(self._view_model.gapList) > 0
        self._btn_repair_all.setEnabled(idle and has_gaps)
        for row_widget in self._row_widgets:
            row_widget.set_enabled(idle)

    def _rebuild_rows(self) -> None:
        for row_widget in self._row_widgets:
            self._rows_layout.removeWidget(row_widget)
            row_widget.deleteLater()
        self._row_widgets = []

        gaps = self._view_model.gapList
        for index, gap in enumerate(gaps):
            row_widget = _GapRowWidget(index, gap, self._on_repair)
            self._rows_layout.insertWidget(index, row_widget)
            self._row_widgets.append(row_widget)

        self._empty_label.setVisible(len(gaps) == 0)
        self._sync_enabled_state()

    def _rebuild_coverage_bar(self) -> None:
        while self._coverage_bar_layout.count():
            item = self._coverage_bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        segments = self._view_model.coverageSegments
        for segment in segments:
            ratio = segment.get("ratio") or 0.05
            stretch = max(2, round(ratio * 1000))
            self._coverage_bar_layout.addWidget(
                _CoverageSegmentWidget(segment), stretch
            )
