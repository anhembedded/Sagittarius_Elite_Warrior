"""What the Backtest screen tells the user when something fails (`BOT-169`).

@details One place for the sentences and the causes, so a presenter or a
coordinator says `reporter.run_failed(detail)` and never writes a failure into
a widget (`ui-presentation-rule.md` §10). A headline is written here, once; the
technical text arrives as `detail`, from `failure_detail(exc)`, and is shown
only behind Details…. A command the user ran is a modal box; a background read
is an inline bar on the Backtest mode (`BACKTEST_ROUTE`) that recovery clears.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
    failure_detail,
)

from .backtest_screen import BACKTEST_ROUTE

CAUSE_RUN = "backtesting.run"
CAUSE_SYNC = "backtesting.sync"
CAUSE_MONTE_CARLO = "backtesting.monte_carlo"
CAUSE_REPORT_IMPORT = "backtesting.report_import"
CAUSE_REPORT_COMPARE = "backtesting.report_compare"
CAUSE_SYMBOL_OPTIONS: Final = "backtesting.symbol_options"
CAUSE_CHART_FEED = "backtesting.chart_feed"
CAUSE_CHART_PREVIEW = "backtesting.chart_preview"


class BacktestFailureReporter:
    """Maps each way the Backtest screen can fail to one `INotifier` call.

    The headlines are class attributes: the presenter also shows one as the
    status label's routine state after a failure.
    """

    RUN: Final = "The backtest could not be completed. Run it again."
    SYNC: Final = (
        "The market data could not be synced. Check the connection and sync again."
    )
    MONTE_CARLO: Final = "The Monte Carlo simulation failed. Run it again."
    REPORT_UNREADABLE: Final = "The report file could not be read. Pick another file."
    REPORT_INVALID: Final = (
        "The file is not a valid backtest report. Pick another file."
    )
    CHART_FEED: Final = (
        "The candles under this run could not be read, so the chart is empty."
    )
    CHART_PREVIEW: Final = (
        "The chart preview could not be read. Change the range or retry."
    )

    SYMBOL_OPTIONS: Final = (
        "The symbol list could not be loaded from the exchange. Saved symbols stay."
    )

    def __init__(self, notifier: INotifier) -> None:
        self._notifier = notifier

    @property
    def notifier(self) -> INotifier:
        """For a collaborator that tells the user on its own (the script runner)."""
        return self._notifier

    @property
    def scope(self) -> str:
        """The mode whose message bar carries this screen's background failures."""
        return BACKTEST_ROUTE

    def run_failed(self, detail: str) -> None:
        self._command(CAUSE_RUN, self.RUN, detail)

    def sync_failed(self, detail: str) -> None:
        self._command(CAUSE_SYNC, self.SYNC, detail)

    def monte_carlo_failed(self, detail: str) -> None:
        self._command(CAUSE_MONTE_CARLO, self.MONTE_CARLO, detail)

    def report_unreadable(self, exc: OSError) -> None:
        self._command(CAUSE_REPORT_IMPORT, self.REPORT_UNREADABLE, failure_detail(exc))

    def report_invalid(self, detail: str) -> None:
        self._command(CAUSE_REPORT_IMPORT, self.REPORT_INVALID, detail)

    def comparison_report_failed(self, detail: str) -> None:
        self._command(CAUSE_REPORT_COMPARE, self.REPORT_INVALID, detail)

    def chart_feed_failed(self, detail: str) -> None:
        self._background(CAUSE_CHART_FEED, self.CHART_FEED, detail, None)

    def symbol_options_failed(self, detail: str) -> None:
        self._background(CAUSE_SYMBOL_OPTIONS, self.SYMBOL_OPTIONS, detail, None)

    def chart_feed_recovered(self) -> None:
        self._notifier.clear_failure(CAUSE_CHART_FEED)

    def chart_preview_failed(self, detail: str, retry: Callable[[], None]) -> None:
        self._background(CAUSE_CHART_PREVIEW, self.CHART_PREVIEW, detail, retry)

    def chart_preview_recovered(self) -> None:
        self._notifier.clear_failure(CAUSE_CHART_PREVIEW)

    def _command(self, cause: str, headline: str, detail: str) -> None:
        self._notifier.report_failure(
            FailureNotice(
                kind=FailureKind.COMMAND,
                cause=cause,
                headline=headline,
                detail=detail,
            )
        )

    def _background(
        self,
        cause: str,
        headline: str,
        detail: str,
        retry: Callable[[], None] | None,
    ) -> None:
        self._notifier.report_failure(
            FailureNotice(
                kind=FailureKind.BACKGROUND,
                cause=cause,
                headline=headline,
                scope=BACKTEST_ROUTE,
                detail=detail,
                retry=retry,
            )
        )
