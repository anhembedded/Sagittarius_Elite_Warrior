"""`EPIC-003F5b` — how the last backtest run came out, lifted out of
`BackTestViewModel`.

@details Fifth slice of `EPIC-003F` (second half), under the same rule as
`003F1`–`003F4`: this class owns the state, `BackTestViewModel` forwards to
it, and **no call site changes**.

@par One run, one set of answers
Result line, stat cards, extended-metrics snapshot, warning line,
limitations list — every one of them is written by the Presenter in the
same breath when a run finishes, and every one of them must be cleared
together when a run starts. Keeping them in one object is what makes
"clear the previous run" a thing you can do in one call instead of five
that can be forgotten one at a time.

@par Data availability is here on purpose
`needsDataSync` and `dataCoverageMessage` look like configuration but are
not: both are set from the *outcome* of a run ("no historical data"), and
`backtest_top_panel.py` reads them in a single expression —
`bool(vm.needsDataSync) and vm.dataCoverageMessage != ""` — to decide
whether the coverage banner shows at all. Two owners for one banner's two
halves is how a banner ends up half-stale.

@par Empty means "nothing yet", everywhere
Empty string / empty list is the no-result convention across all of these
(`set_stat_cards([], [])`, `set_limitations([])`, `set_result_warning_text("")`),
and the widgets hide their rows on it rather than rendering a blank line.
`extended_metrics_snapshot` uses `None` for the same reason: it is a
dataclass, not a list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, Signal, Slot

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.extended_metrics_snapshot import (
        ExtendedMetricsSnapshot,
    )
    from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_comparison_snapshot import (
        ReportComparisonSnapshot,
    )


class RunResultViewModel(QObject):
    """@brief The last run's verdict: text, cards, warnings, limits."""

    resultChanged = Signal()
    statCardsChanged = Signal()
    resultWarningTextChanged = Signal()
    limitationsChanged = Signal()
    dataCoverageChanged = Signal()
    needsDataSyncChanged = Signal()
    drawdownPointsChanged = Signal()
    yearlyReturnsChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._result_text = ""
        self._result_is_error = False
        self._primary_stat_cards: list[dict[str, str]] = []
        self._extended_stat_cards: list[dict[str, str]] = []
        #: `EPIC-015` Phase 3 — `MetricsDetailDialogWidget`'s composition
        #: root reads this directly (plain Python, not a QML `Property`).
        #: `None` until the first run succeeds, the same "no result yet"
        #: convention `_extended_stat_cards` uses via an empty list.
        self._extended_metrics_snapshot: ExtendedMetricsSnapshot | None = None
        #: `BOT-115D` — the config+result pair behind whatever is currently
        #: on screen, for the report comparison dialog's Column A. Same
        #: "plain Python accessor, not a QML `Property`" reasoning as
        #: `_extended_metrics_snapshot` above: only that dialog's
        #: composition root reads it.
        self._comparison_snapshot: ReportComparisonSnapshot | None = None
        self._result_warning_text = ""
        self._limitations: list[str] = []
        self._is_data_fully_covered = False
        self._data_coverage_message = ""
        self._needs_data_sync = False
        #: `BOT-106D` — drawdown underwater chart points and yearly returns
        #: heatmap rows, same "empty means no result yet" convention as
        #: `_primary_stat_cards` above.
        self._drawdown_points: list[dict[str, float]] = []
        self._yearly_returns: list[dict[str, object]] = []

    # ------------------------------------------------------------------ #
    # Result line
    # ------------------------------------------------------------------ #

    def _get_result_text(self) -> str:
        return self._result_text

    resultText = Property(str, _get_result_text, notify=resultChanged)

    def _get_result_is_error(self) -> bool:
        return self._result_is_error

    resultIsError = Property(bool, _get_result_is_error, notify=resultChanged)

    @Slot(str, bool)
    def set_result(self, text: str, is_error: bool) -> None:
        self._result_text = text
        self._result_is_error = is_error
        self.resultChanged.emit()

    # ------------------------------------------------------------------ #
    # Stat cards (BOT-055)
    # ------------------------------------------------------------------ #

    def _get_primary_stat_cards(self) -> list[dict[str, str]]:
        return self._primary_stat_cards

    primaryStatCards = Property(
        "QVariantList", _get_primary_stat_cards, notify=statCardsChanged
    )

    def _get_extended_stat_cards(self) -> list[dict[str, str]]:
        return self._extended_stat_cards

    extendedStatCards = Property(
        "QVariantList", _get_extended_stat_cards, notify=statCardsChanged
    )

    @Slot("QVariantList", "QVariantList")
    def set_stat_cards(
        self,
        primary: list[dict[str, str]],
        extended: list[dict[str, str]],
    ) -> None:
        """Empty lists clear the panel (no result yet, or the last run
        failed / returned nothing) — the cards row hides itself when
        `primaryStatCards` is empty."""
        self._primary_stat_cards = primary
        self._extended_stat_cards = extended
        self.statCardsChanged.emit()

    def extended_metrics_snapshot(self) -> ExtendedMetricsSnapshot | None:
        """Plain Python accessor (no `Property`) for
        `MetricsDetailDialogWidget`'s composition root — see the field's
        own docstring in `__init__`, and `ExtendedMetricsSnapshot`'s module
        docstring, for why this is a separate retention from
        `extendedStatCards` rather than the same list re-read."""
        return self._extended_metrics_snapshot

    @Slot(object)
    def set_extended_metrics_snapshot(
        self, snapshot: ExtendedMetricsSnapshot | None
    ) -> None:
        """Set by `BackTestPresenter` right alongside `set_stat_cards(...)`.
        `None` clears it.

        `@Slot(object)` even though nothing QML-side calls it: every other
        `set_*` mutator carries `@Slot`, and `unprotected_mutators()`
        (`BUG-031`'s guard) flags any `set_*`/`append*`/`clear*`/`hide_*`
        with neither `@Slot` nor `@ui_mutator`. `object` is PySide6's
        accept-any-Python-value slot type, which is what an
        `ExtendedMetricsSnapshot | None` needs — it is not a Qt-registrable
        type on its own."""
        self._extended_metrics_snapshot = snapshot

    def comparison_snapshot(self) -> ReportComparisonSnapshot | None:
        """Plain Python accessor (no `Property`), same shape as
        `extended_metrics_snapshot()` — `ReportComparisonDialog`'s
        composition root reads it for Column A."""
        return self._comparison_snapshot

    @Slot(object)
    def set_comparison_snapshot(
        self, snapshot: ReportComparisonSnapshot | None
    ) -> None:
        """Set by `BackTestPresenter._present_result()` right alongside
        `set_extended_metrics_snapshot(...)`, cleared wherever that one is.
        `@Slot(object)` for the same `unprotected_mutators()` reason that
        method documents."""
        self._comparison_snapshot = snapshot

    # ------------------------------------------------------------------ #
    # Warning + limitations
    # ------------------------------------------------------------------ #

    def _get_result_warning_text(self) -> str:
        return self._result_warning_text

    resultWarningText = Property(
        str, _get_result_warning_text, notify=resultWarningTextChanged
    )

    @Slot(str)
    def set_result_warning_text(self, text: str) -> None:
        """`BOT-079` follow-up. Empty string means "no warning" — the row
        hides entirely rather than showing a blank line."""
        if text != self._result_warning_text:
            self._result_warning_text = text
            self.resultWarningTextChanged.emit()

    def _get_limitations(self) -> list[str]:
        return self._limitations

    limitations = Property("QStringList", _get_limitations, notify=limitationsChanged)

    @Slot("QStringList")
    def set_limitations(self, limitations: list[str]) -> None:
        """`BOT-081`. Empty list means "no result yet" — same convention as
        `set_stat_cards([], [])`."""
        self._limitations = list(limitations)
        self.limitationsChanged.emit()

    # ------------------------------------------------------------------ #
    # Data availability (BOT-059)
    # ------------------------------------------------------------------ #

    def _get_is_data_fully_covered(self) -> bool:
        return self._is_data_fully_covered

    isDataFullyCovered = Property(
        bool, _get_is_data_fully_covered, notify=dataCoverageChanged
    )

    def _get_data_coverage_message(self) -> str:
        return self._data_coverage_message

    dataCoverageMessage = Property(
        str, _get_data_coverage_message, notify=dataCoverageChanged
    )

    @Slot(bool, str)
    def set_data_coverage(self, is_fully_covered: bool, message: str) -> None:
        self._is_data_fully_covered = is_fully_covered
        self._data_coverage_message = message
        self.dataCoverageChanged.emit()

    def _get_needs_data_sync(self) -> bool:
        return self._needs_data_sync

    #: True only after a run comes back "no historical data" — drives the
    #: "Đồng bộ ngay" button's visibility. Read-only from the View by
    #: design: only the Presenter knows whether the last run hit that case.
    needsDataSync = Property(bool, _get_needs_data_sync, notify=needsDataSyncChanged)

    @Slot(bool)
    def set_needs_data_sync(self, value: bool) -> None:
        if value != self._needs_data_sync:
            self._needs_data_sync = value
            self.needsDataSyncChanged.emit()

    # ------------------------------------------------------------------ #
    # Drawdown chart + monthly/yearly returns heatmap (BOT-106D)
    # ------------------------------------------------------------------ #

    def _get_drawdown_points(self) -> list[dict[str, float]]:
        return self._drawdown_points

    drawdownPoints = Property(
        "QVariantList", _get_drawdown_points, notify=drawdownPointsChanged
    )

    @Slot("QVariantList")
    def set_drawdown_points(self, points: list[dict[str, float]]) -> None:
        """Empty list means "no result yet" — same convention as
        `set_stat_cards([], [])`. `points` is `logic/performance_charts.py`'s
        `build_drawdown_chart_points()` output."""
        self._drawdown_points = points
        self.drawdownPointsChanged.emit()

    def _get_yearly_returns(self) -> list[dict[str, object]]:
        return self._yearly_returns

    yearlyReturns = Property(
        "QVariantList", _get_yearly_returns, notify=yearlyReturnsChanged
    )

    @Slot("QVariantList")
    def set_yearly_returns(self, rows: list[dict[str, object]]) -> None:
        """`rows` is `logic/performance_charts.py`'s
        `build_yearly_returns_rows()` output."""
        self._yearly_returns = rows
        self.yearlyReturnsChanged.emit()
