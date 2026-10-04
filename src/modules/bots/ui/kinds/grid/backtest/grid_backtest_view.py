"""`EPIC-029D` — the Grid's Backtest page: a period, Run, and what came out.

The page asks for an interval and a period, runs on Run, and shows:
· the replayed candles with the plan's levels, the fills and the exits,
  drawn by a `BotChart` (ADR D16, the PR #321 review: never a drawer of
  its own);
· the equity against buy-and-hold (D18);
· the summary, each figure with its caveat, the fill rule among them.

While a run is in flight only Cancel is live. A refusal for candles that are
not stored offers "Sync candles", and only a click syncs (`BUG-107`). Stock
controls, no style sheet (`ui-presentation-rule.md`).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from PySide6.QtCore import QDateTime, Qt, QTimeZone, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    EquityPoint,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_chart import BotChart
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.equity_chart import (
    EquityChart,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_summary import (
    SummaryRow,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)

#: The intervals a Grid backtest offers; the result chart draws in the same one.
INTERVALS = (
    TimeFrame.ONE_MINUTE,
    TimeFrame.FIVE_MINUTES,
    TimeFrame.FIFTEEN_MINUTES,
    TimeFrame.ONE_HOUR,
)
_DEFAULT_INTERVAL = TimeFrame.FIFTEEN_MINUTES
_DEFAULT_DAYS = 7
_UTC = QTimeZone.utc()


class GridBacktestView(QWidget):
    """@brief The period, the three commands, and the result."""

    run_requested = Signal()
    cancel_requested = Signal()
    sync_requested = Signal()

    def __init__(
        self, chart_ports: LiveChartPorts, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.interval = QComboBox()
        self.interval.setObjectName("cmbGridBacktestInterval")
        for interval in INTERVALS:
            self.interval.addItem(interval.value, interval.value)
        self.interval.setCurrentIndex(INTERVALS.index(_DEFAULT_INTERVAL))
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        self.start = _datetime_edit(
            "dtGridBacktestStart", now - timedelta(days=_DEFAULT_DAYS)
        )
        self.end = _datetime_edit("dtGridBacktestEnd", now)
        self.run_button = QPushButton("Run backtest")
        self.run_button.setObjectName("btnGridBacktestRun")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("btnGridBacktestCancel")
        self.sync_button = QPushButton("Sync candles")
        self.sync_button.setObjectName("btnGridBacktestSync")
        self.status = QLabel()
        self.status.setObjectName("lblGridBacktestStatus")
        self.status.setWordWrap(True)
        self.card = ChartCard("Backtest")
        self.chart = BotChart(self.card, chart_ports, parent=self.card)
        self.equity = EquityChart()
        self.summary = QFormLayout()
        self._build()
        self.run_button.clicked.connect(self.run_requested)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.sync_button.clicked.connect(self.sync_requested)
        self.show_idle("")

    # -- what the presenter reads ----------------------------------------- #

    def chosen_interval(self) -> TimeFrame:
        return TimeFrame(str(self.interval.currentData()))

    def chosen_period(self) -> tuple[datetime, datetime]:
        return _utc(self.start), _utc(self.end)

    # -- what the presenter shows ----------------------------------------- #

    def show_idle(self, reason: str) -> None:
        """Ready to run; `reason` says why Run is off, empty when it is on."""
        self.run_button.setEnabled(not reason)
        self.run_button.setToolTip(reason)
        self.cancel_button.setEnabled(False)
        self.sync_button.setVisible(False)
        if reason:
            self.status.setText(reason)

    def show_running(self, text: str, *, side_effects: bool = False) -> None:
        """In flight: only Cancel is live, "Stop" when the work stores data
        (a sync), since what it stored stays (MS `progress-bars`)."""
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("Stop" if side_effects else "Cancel")
        self.sync_button.setVisible(False)
        self.status.setText(text)

    def show_refusal(self, reason: str, *, offer_sync: bool) -> None:
        self.show_idle("")
        self.sync_button.setVisible(offer_sync)
        self.status.setText(reason)

    def offer_sync(self, reason: str) -> None:
        """Idle, with "Sync candles" offered for what `reason` says is missing."""
        self.sync_button.setVisible(True)
        self.status.setText(reason)

    def show_replay(
        self,
        candles: Sequence[MarketData],
        overlay: BotOverlay,
        equity: Sequence[EquityPoint],
        rows: Sequence[SummaryRow],
    ) -> None:
        self.show_idle("")
        self.status.setText("Backtest done.")
        self.chart.draw_history(candles)
        self.chart.show_overlay(overlay)
        self.equity.show_equity(equity)
        _fill_summary(self.summary, rows)

    def clear_result(self) -> None:
        self.chart.draw_history(())
        self.chart.show_overlay(BotOverlay())
        self.equity.clear()
        _fill_summary(self.summary, ())

    def summary_text(self) -> dict[str, str]:
        """The summary as shown, label to value (tests read it)."""
        shown: dict[str, str] = {}
        for row in range(self.summary.rowCount()):
            label = self.summary.itemAt(row, QFormLayout.ItemRole.LabelRole)
            value = self.summary.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if label is not None and value is not None:
                label_widget, value_widget = label.widget(), value.widget()
                if isinstance(label_widget, QLabel) and isinstance(
                    value_widget, QLabel
                ):
                    shown[label_widget.text()] = value_widget.text()
        return shown

    def shutdown(self) -> None:
        self.chart.shutdown()
        self.card.cleanup()

    def _build(self) -> None:
        period = QHBoxLayout()
        for label, field in (
            ("Interval", self.interval),
            ("From", self.start),
            ("To", self.end),
        ):
            period.addWidget(QLabel(label))
            period.addWidget(field)
        period.addWidget(self.run_button)
        period.addWidget(self.cancel_button)
        period.addWidget(self.sync_button)
        period.addStretch(1)
        figures = QWidget()
        figures.setLayout(self.summary)
        lower = QSplitter()
        lower.addWidget(self.equity)
        lower.addWidget(figures)
        body = QSplitter(Qt.Orientation.Vertical)
        body.addWidget(self.card)
        body.addWidget(lower)
        layout = QVBoxLayout(self)
        layout.addLayout(period)
        layout.addWidget(self.status)
        layout.addWidget(body, 1)


def _datetime_edit(name: str, value: datetime) -> QDateTimeEdit:
    edit = QDateTimeEdit()
    edit.setObjectName(name)
    edit.setCalendarPopup(True)
    edit.setTimeZone(_UTC)
    edit.setDisplayFormat("yyyy-MM-dd HH:mm 'UTC'")
    edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(value.timestamp()), _UTC))
    return edit


def _utc(edit: QDateTimeEdit) -> datetime:
    return datetime.fromtimestamp(edit.dateTime().toSecsSinceEpoch(), UTC)


def _fill_summary(form: QFormLayout, rows: Sequence[SummaryRow]) -> None:
    while form.rowCount():
        form.removeRow(0)
    for row in rows:
        value = QLabel(row.value)
        value.setWordWrap(True)
        form.addRow(QLabel(row.label), value)
