"""How a live chart tells the user a background failure (`BOT-169`, `BUG-172`).

One notice per chart cause: a stream that could not open and a history that could
not be loaded both say a sentence the author wrote, keep the technical text behind
Details…, and offer a Retry — which differs: a stream's goes live again, a load's
only loads again.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)


@dataclass(frozen=True)
class ChartFailureChannel:
    """Where one chart tells its failures: its cause, the mode whose bar shows
    them, and the log line the chip's status carries."""

    notifier: INotifier
    cause: str
    scope: str
    log: Callable[[str], None]

    @classmethod
    def of(
        cls, ports: LiveChartPorts, log: Callable[[str], None]
    ) -> ChartFailureChannel:
        """The channel of the chart that `ports` assembles."""
        return cls(
            ports.notifier,
            f"charting.live_stream.{ports.stream_owner}",
            ports.scope,
            log,
        )

    def tell(self, headline: str, detail: str, retry: Callable[[], None]) -> None:
        """The sentence goes to the log and the bar; `detail` only behind the
        bar's Details… (`BOT-169`)."""
        self.log(f"[ERROR] {headline}")
        self.notifier.report_failure(
            FailureNotice(
                kind=FailureKind.BACKGROUND,
                cause=self.cause,
                headline=headline,
                scope=self.scope,
                detail=detail,
                retry=retry,
            )
        )

    def clear(self) -> None:
        """The chart recovered: its bar goes."""
        self.notifier.clear_failure(self.cause)
