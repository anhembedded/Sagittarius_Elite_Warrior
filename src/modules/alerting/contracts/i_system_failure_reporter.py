"""`ISystemFailureReporter` - how the shell tells the module the app itself failed (`EPIC-036B`).

A failure of the app (a background task that died, a bulk sync that failed, a UI slot that
raised) is not a bot's or a venue's event, so no `contracts/` of another module carries it and
`alerting` cannot subscribe to it without importing the shell's normalisers. The shell
normalises the failure once (`system_error_report.py`) and hands the text over this port.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ISystemFailureReporter(ABC):
    """Cheap and non-blocking, like `IAlertPublisher`; never raises into the caller."""

    @abstractmethod
    def report_failure(self, source: str, summary: str) -> None:
        """One failure: `source` names where it came from (a task or a slot name) in words
        the owner recognises, `summary` is the one-line text: the exception's type and message
        are in it, so a source must not raise with a secret in its message. The traceback is not
        passed; it stays in the run log. The channel sanitises what it posts (`EPIC-036C`)."""
