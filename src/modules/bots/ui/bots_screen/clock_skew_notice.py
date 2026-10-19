"""`BOT-182` — the Bots screen tells the owner when this machine's clock is far from the exchange's.

@details Signed requests are corrected by the session's offset, so a skewed
clock breaks nothing the app sends; but `run_started_at`, the times in the log
and on the screens and the start of a history read come from the local clock,
and they are that far off. The Connect step already measures the skew with every
account read, so this only judges and tells it, through `INotifier`: one bar per
venue, above `CLOCK_SKEW_LIMIT_MS` in either direction, gone when the skew is
back under it or the venue cannot be read (the connection failure has its own
bar). It is told once per episode, so a bar the owner dismissed does not come
back with the next read. It refuses nothing: no start, resume or order depends
on it. The headless pre-flight and health probe judge the same clock on their own.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.clock_skew_limit import (
    CLOCK_SKEW_LIMIT_MS,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)


def clock_skew_cause(source: AccountSource) -> str:
    return f"bots.clock_skew.{source.value}"


def clock_skew_headline(source: AccountSource, skew_ms: int) -> str:
    """@param skew_ms This machine's clock minus the exchange's: positive is ahead."""
    size = f"{round(abs(skew_ms) / 1000)} s"
    side = "ahead of" if skew_ms > 0 else "behind"
    return (
        f"This computer's clock is {size} {side} {source.venue_title}'s. Times shown "
        "and in the log come from it. Orders use the exchange's time; sync the clock."
    )


class ClockSkewNotice:
    """@brief One skew bar per venue, told while that venue's skew is over the limit."""

    def __init__(self, notifier: INotifier) -> None:
        self._notifier = notifier
        self._told: set[AccountSource] = set()

    def observe(self, source: AccountSource, skew_ms: int | None) -> None:
        """A read of `source`'s account measured `skew_ms` (`None`: it carried none)."""
        if skew_ms is None or abs(skew_ms) <= CLOCK_SKEW_LIMIT_MS:
            self.forget(source)
            return
        if source in self._told:
            return
        self._told.add(source)
        self._notifier.report_failure(
            FailureNotice(
                FailureKind.BACKGROUND,
                clock_skew_cause(source),
                clock_skew_headline(source, skew_ms),
                scope=BOTS_ROUTE,
            )
        )

    def forget(self, source: AccountSource) -> None:
        """The venue cannot be read now, or its skew is back under the limit."""
        if source in self._told:
            self._told.discard(source)
            self._notifier.clear_failure(clock_skew_cause(source))

    def keep_only(self, source: AccountSource | None) -> None:
        """The screen moved to a bot on `source` (`None`: to none): another
        venue's bar is not about what is shown."""
        for told in tuple(self._told):
            if told is not source:
                self.forget(told)
