"""`BOT-169` — how a Database-screen worker tells the user a job failed.

@details Every coordinator's worker catches, then does the same three things:
logs the exception, writes a sentence into the screen's log list, and tells the
`INotifier`. The exception's text goes to the logger and, as `detail`, to the
notifier; the log list and the headline carry only the sentence the caller
wrote (`ui-presentation-rule.md` §10).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
    failure_detail,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.database_screen import (
    DATABASE_ROUTE,
)

logger = logging.getLogger("App.DataManagement")


class FailureReporter:
    """Reports a failed Database-screen job on the one surface the kind decides."""

    def __init__(
        self, notifier: INotifier, ui_error_log_signal: Callable[[str], None]
    ) -> None:
        self._notifier = notifier
        self._ui_error_log_signal = ui_error_log_signal

    def command_failed(self, cause: str, headline: str, exc: Exception) -> None:
        """A job the user started failed: a modal box, plus the headline in the log list."""
        logger.error(f"[data-management] {cause} failed", exc_info=exc)
        self._ui_error_log_signal(headline)
        self._notifier.report_failure(
            FailureNotice(
                kind=FailureKind.COMMAND,
                cause=cause,
                headline=headline,
                detail=failure_detail(exc),
            )
        )

    def background_failed(
        self,
        cause: str,
        headline: str,
        exc: Exception,
        retry: Callable[[], None] | None = None,
    ) -> None:
        """A read on opening failed: a message bar on the Database mode, with Retry."""
        logger.error(f"[data-management] {cause} failed", exc_info=exc)
        self._ui_error_log_signal(headline)
        self._notifier.report_failure(
            FailureNotice(
                kind=FailureKind.BACKGROUND,
                cause=cause,
                headline=headline,
                scope=DATABASE_ROUTE,
                detail=failure_detail(exc),
                retry=retry,
            )
        )

    def recovered(self, cause: str) -> None:
        """The read that failed under `cause` succeeded: its bar goes."""
        self._notifier.clear_failure(cause)
