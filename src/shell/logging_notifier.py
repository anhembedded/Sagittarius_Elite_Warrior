"""`LoggingNotifier` — the `INotifier` of a run with no window (`BOT-169`).

The command line and a headless run have no screen to put a message on, so the
failures and events a module reports go to the log, which is where a person
running headless looks. The GUI entry point replaces it with the Qt presenter
before any screen is built (`app_bootstrapper.py`).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureNotice

logger = logging.getLogger("App.Shell.Notifier")


class LoggingNotifier:
    """Writes every notice to the run log; shows nothing."""

    def report_failure(self, notice: FailureNotice) -> None:
        logger.warning(
            "%s failure %s: %s (%s) [notice-headless]",
            notice.kind.value,
            notice.cause,
            notice.headline,
            notice.detail,
        )

    def clear_failure(self, cause: str) -> None:
        logger.info("Failure %s cleared [notice-headless]", cause)

    def notify(self, headline: str, detail: str = "") -> None:
        logger.info("Notice: %s [notice-headless]", headline)
