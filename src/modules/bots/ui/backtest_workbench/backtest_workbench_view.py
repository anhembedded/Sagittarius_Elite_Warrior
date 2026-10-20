"""`EPIC-040D` — the Backtest workbench's page: a sandbox of the bot's plan, a period, Run, and what
came out; the same for every kind of bot.

Above the panes, the period on one row and the commands with the status line on the next, so the
page's minimum width leaves the Bots mode a 1024-wide window and its height a 700-high one
(`EPIC-040E`: the period and commands on one row were 850 px wide).

Setup (left): the bot the sandbox was copied from, the kind's own editor (a second instance, never
bound to the Bots menu's commands), what differs from the bot's plan, and the verdicts the symbol's
rules gave it. Results (right), one tab each: the replayed candles with the plan's levels and the
fills, the equity against buy-and-hold, the figures with their caveats, and the fills. They are tabs,
not a column, so the page's minimum height leaves the Bots mode a 1024×700 window (`EPIC-040E`).

The view applies a `WorkbenchState` and forwards gestures: it decides nothing (`pitfalls/ui.md` §4).
Stock controls, no style sheet, no fixed sizes (`ui-presentation-rule.md`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from PySide6.QtCore import QDateTime, Qt, QTimeZone, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestFill,
    EquityPoint,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.equity_pane import (
    EquityPane,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.outcome_view import (
    FillsTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_state import (
    WorkbenchState,
    controls_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.workbench_words import (
    BANNER,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.chart.bot_chart import BotChart
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import (
    Readout,
    ReadoutSlot,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable

#: The intervals a backtest offers; the result chart draws in the same one.
INTERVALS = (
    TimeFrame.ONE_MINUTE,
    TimeFrame.FIVE_MINUTES,
    TimeFrame.FIFTEEN_MINUTES,
    TimeFrame.ONE_HOUR,
)
DEFAULT_INTERVAL = TimeFrame.FIFTEEN_MINUTES
_DEFAULT_DAYS = 7
_UTC = QTimeZone.utc()


@dataclass(frozen=True, slots=True)
class OutcomeShown:
    """Everything the result panes draw for one outcome."""

    candles: Sequence[MarketData]
    overlay: BotOverlay
    equity: Sequence[EquityPoint]
    readout: Readout
    notes: Sequence[str]
    fills: Sequence[BacktestFill]


class BacktestWorkbenchView(QWidget):
    """@brief The setup, the commands, and the result."""

    run_requested = Signal()
    cancel_requested = Signal()
    sync_requested = Signal()
    #: The person chose to replay a Futures period without its funding (`EPIC-039K`, O9).
    run_without_funding_requested = Signal()
    reset_requested = Signal()
    #: The answers to "replace your edits with the other bot's saved plan?".
    replace_edits_requested = Signal()
    keep_edits_requested = Signal()
    #: The editor's parameters after every edit by the person.
    config_edited = Signal(object)

    def __init__(
        self, chart_ports: LiveChartPorts, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.interval = QComboBox()
        self.interval.setObjectName("cmbBacktestInterval")
        for interval in INTERVALS:
            self.interval.addItem(interval.value, interval.value)
        self.interval.setCurrentIndex(INTERVALS.index(DEFAULT_INTERVAL))
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        self.start = _datetime_edit(
            "dtBacktestStart", now - timedelta(days=_DEFAULT_DAYS)
        )
        self.end = _datetime_edit("dtBacktestEnd", now)
        self.run_button = _button("Run backtest", "btnBacktestRun")
        self.cancel_button = _button("Cancel", "btnBacktestCancel")
        self.sync_button = _button("Sync candles", "btnBacktestSync")
        self.no_funding_button = _button("Run without funding", "btnBacktestNoFunding")
        self.no_funding_button.setToolTip(
            "Replays the period with no funding charged. The result says so, and a "
            "leveraged bot looks better than it was."
        )
        self.reset_button = _button("Reset to the bot's plan", "btnBacktestReset")
        self.status = _wrapped_label("lblBacktestStatus")
        self.banner = _wrapped_label("lblBacktestBanner", BANNER)
        self.source = _wrapped_label("lblBacktestSource")
        self.changed = _wrapped_label("lblBacktestChanged")
        self.verdicts = _wrapped_label("lblBacktestVerdicts")
        self.question = _wrapped_label("lblBacktestQuestion")
        self.replace_button = _button("Replace my edits", "btnBacktestReplaceEdits")
        self.keep_button = _button("Keep my edits", "btnBacktestKeepEdits")
        self._editor_host = QWidget()
        self._editor_layout = QVBoxLayout(self._editor_host)
        self._editor_layout.setContentsMargins(0, 0, 0, 0)
        self._editor: BotKindPanel | None = None
        self.card = ChartCard("Backtest")
        self.chart = BotChart(self.card, chart_ports, parent=self.card)
        self.equity = EquityPane()
        self.summary = ReadoutSlot()
        self.summary.setObjectName("roBacktestFigures")
        self.notes = _wrapped_label("lblBacktestCaveats")
        self.fills_model = FillsTableModel()
        self.fills = SpecTable(
            self.fills_model,
            object_name="tblBacktestFills",
            empty_text="Run a backtest to see its fills.",
        )
        self._build()
        self.run_button.clicked.connect(self.run_requested)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.sync_button.clicked.connect(self.sync_requested)
        self.no_funding_button.clicked.connect(self.run_without_funding_requested)
        self.reset_button.clicked.connect(self.reset_requested)
        self.replace_button.clicked.connect(self.replace_edits_requested)
        self.keep_button.clicked.connect(self.keep_edits_requested)
        self.show_state(WorkbenchState())

    # -- what the presenter reads ----------------------------------------- #

    def chosen_interval(self) -> TimeFrame:
        return TimeFrame(str(self.interval.currentData()))

    def chosen_period(self) -> tuple[datetime, datetime]:
        return _utc(self.start), _utc(self.end)

    # -- what the presenter shows ----------------------------------------- #

    def show_state(self, state: WorkbenchState) -> None:
        """Shows `state`: the commands, the offers, the words."""
        controls = controls_of(state)
        self.run_button.setEnabled(controls.run_enabled)
        self.run_button.setToolTip(state.reason)
        self.cancel_button.setEnabled(controls.cancel_enabled)
        self.cancel_button.setText(controls.cancel_text)
        self.sync_button.setVisible(controls.sync_visible)
        self.no_funding_button.setVisible(controls.no_funding_visible)
        self.reset_button.setEnabled(controls.reset_enabled)
        self.status.setText(state.status)
        self.source.setText(state.source_text)
        self.changed.setText(_changed_text(state))
        self.verdicts.setText("\n".join(state.verdict_lines))
        self.question.setText(state.question)
        for widget in (self.question, self.replace_button, self.keep_button):
            widget.setVisible(controls.answer_visible)
        if self._editor is not None:
            self._editor.set_editable(controls.editor_enabled)

    @property
    def editor(self) -> BotKindPanel | None:
        """The kind's editor now in the setup column, if any."""
        return self._editor

    def set_editor(self, editor: BotKindPanel | None) -> None:
        """Puts the kind's editor in the setup column (a second instance, `EPIC-040C`); `None`
        for a bot with none."""
        if editor is self._editor:
            return
        if self._editor is not None:
            self._editor.config_changed.disconnect(self.config_edited)
            self._editor_layout.removeWidget(self._editor)
            self._editor.hide()
            self._editor.deleteLater()
        self._editor = editor
        if editor is not None:
            self._editor_layout.addWidget(editor)
            editor.config_changed.connect(self.config_edited)

    def show_outcome(self, shown: OutcomeShown) -> None:
        self.chart.draw_history(shown.candles)
        self.chart.show_overlay(shown.overlay)
        self.equity.show_equity(shown.equity)
        self.summary.show_readout(shown.readout)
        self.notes.setText("\n".join(shown.notes))
        self.fills_model.set_rows(list(shown.fills))

    def use_display_timezone(self, preference: DisplayTimezonePreference) -> None:
        """The replay chart and the equity curve read in the shared display time zone; the chart
        offers its drop-down."""
        self.chart.use_display_timezone(preference)
        self.equity.follow_display_timezone(preference)

    def clear_result(self) -> None:
        self.chart.draw_history(())
        self.chart.show_overlay(BotOverlay())
        self.equity.clear()
        self.summary.clear()
        self.notes.clear()
        self.fills_model.set_rows([])

    def summary_text(self) -> dict[str, str]:
        """The figures as shown, row key to text (tests read it)."""
        return {key: self.summary.value_text(key) or "" for key in self.summary.keys}

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
            period.addWidget(plain_label(label))
            period.addWidget(field)
        period.addStretch(1)
        commands = QHBoxLayout()
        for button in (
            self.run_button,
            self.cancel_button,
            self.sync_button,
            self.no_funding_button,
            self.reset_button,
        ):
            commands.addWidget(button)
        commands.addWidget(self.status, 1)
        answers = QHBoxLayout()
        answers.addWidget(self.replace_button)
        answers.addWidget(self.keep_button)
        answers.addStretch(1)
        setup = QWidget()
        column = QVBoxLayout(setup)
        column.setContentsMargins(0, 0, 0, 0)
        for widget in (self.source, self.question):
            column.addWidget(widget)
        column.addLayout(answers)
        column.addWidget(self._scrolling(self._editor_host), 1)
        column.addWidget(self.changed)
        column.addWidget(self.verdicts)
        body = QSplitter()
        body.setChildrenCollapsible(False)
        body.addWidget(setup)
        body.addWidget(self._result_tabs())
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(period)
        layout.addLayout(commands)
        layout.addWidget(self.banner)
        layout.addWidget(body, 1)

    def _result_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.setObjectName("tabBacktestResults")
        figures = QWidget()
        column = QVBoxLayout(figures)
        column.addWidget(self.summary)
        column.addWidget(self.notes)
        column.addStretch(1)
        tabs.addTab(self.card, "Replay")
        tabs.addTab(self.equity, "Equity")
        tabs.addTab(self._scrolling(figures), "Figures")
        tabs.addTab(self.fills.body, "Fills")
        return tabs

    @staticmethod
    def _scrolling(content: QWidget) -> QScrollArea:
        """`content` scrolls once, at its own pane, never across (a dozen rows must not set the
        floor of the window, PR #361)."""
        pane = QScrollArea()
        pane.setWidgetResizable(True)
        pane.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pane.setWidget(content)
        return pane


def _button(text: str, name: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(name)
    return button


def _wrapped_label(name: str, text: str = "") -> QLabel:
    label = plain_label(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def _changed_text(state: WorkbenchState) -> str:
    if not state.has_sandbox:
        return ""
    if not state.changed_fields:
        return "The same as the bot's plan."
    return "Changed from the bot's plan: " + ", ".join(state.changed_fields)


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
