"""One WARNING per failure streak of a periodic read, and an INFO when it recovers (`BUG-209`).

A refresh job runs on a fixed interval for the life of the process. A read that fails
every tick must not write a line per tick (`logging-rule.md` §6: never a hot loop), and
must not write nothing either: at DEBUG an unattended run that lost its positions read
for a day looked identical to a healthy one. The shape is the account summary's
(`AccountSummaryRefreshService`): the first failure of a streak is a WARNING, the rest
of it are DEBUG, and the first success after it is one INFO line.
"""

from __future__ import annotations

import logging


class RefreshFailureStreak:
    """Tracks whether the last attempt of one read failed, and logs the edges."""

    def __init__(self, logger: logging.Logger, what: str, venue_name: str) -> None:
        self._logger = logger
        self._what = what
        self._venue_name = venue_name
        self._failures = 0

    def failed(self, error: Exception) -> None:
        self._failures += 1
        if self._failures == 1:
            self._logger.warning(
                "%s on %s failed: %s: %s; the next tries are logged at DEBUG until it "
                "recovers [refresh-failed]",
                self._what,
                self._venue_name,
                type(error).__name__,
                error,
            )
            return
        self._logger.debug(
            "%s on %s still failing (%d in a row): %s",
            self._what,
            self._venue_name,
            self._failures,
            error,
        )

    def succeeded(self) -> None:
        if self._failures:
            self._logger.info(
                "%s on %s recovered after %d failed attempt(s) [refresh-recovered]",
                self._what,
                self._venue_name,
                self._failures,
            )
        self._failures = 0
