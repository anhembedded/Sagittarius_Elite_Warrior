"""`RecordingNotifier` — an `INotifier` that keeps what it was told, for tests (`BOT-169`).

Lives beside the port, as the other contracts' fakes do, so a module's tests
and a screen's preview use one double instead of a copy each.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
)


class RecordingNotifier:
    """Records every failure, clearance and event, in the order told."""

    def __init__(self) -> None:
        self.failures: list[FailureNotice] = []
        self.cleared: list[str] = []
        self.events: list[tuple[str, str]] = []

    def report_failure(self, notice: FailureNotice) -> None:
        self.failures.append(notice)

    def clear_failure(self, cause: str) -> None:
        self.cleared.append(cause)

    def notify(self, headline: str, detail: str = "") -> None:
        self.events.append((headline, detail))

    def failures_of(self, kind: FailureKind) -> list[FailureNotice]:
        return [n for n in self.failures if n.kind is kind]

    @property
    def last(self) -> FailureNotice:
        return self.failures[-1]
