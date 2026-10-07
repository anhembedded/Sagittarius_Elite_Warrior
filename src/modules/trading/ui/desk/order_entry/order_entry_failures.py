"""`BOT-169` — what the order panel tells the user when something fails.

@details Every failure of the panel goes through `INotifier`, none is written
into a widget as an exception's text (`ui-presentation-rule.md` §10): the
terms read that failed is a message bar at the top of the Trade mode with
Retry; a check or a send the user pressed that failed is a message box. The
panel's own line says only a constant sentence.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.failure_cause import (
    failure_cause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_entry.order_entry_presenter_writer import (
    OrderEntryPresenterWriter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.order_failure import (
    SubmitFailure,
    submit_failure_headline,
    submit_failure_notice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class OrderEntryFailures:
    """@brief Tells the user of one order panel's failures."""

    def __init__(
        self,
        notifier: INotifier,
        venue: TradingVenue,
        writes: OrderEntryPresenterWriter,
    ) -> None:
        self._notifier = notifier
        self._venue = venue
        self._writes = writes
        self._terms_cause = failure_cause(venue, "order_terms")

    def terms_unread(self, symbol: str, detail: str, retry: Callable[[], None]) -> None:
        self._writes.show_error(f"{symbol} could not be read.")
        self._notifier.report_failure(
            FailureNotice(
                FailureKind.BACKGROUND,
                self._terms_cause,
                f"The order panel could not read {symbol}. Check the connection "
                "and retry.",
                scope=TRADE_ROUTE,
                detail=detail,
                retry=retry,
            )
        )

    def terms_read(self) -> None:
        self._notifier.clear_failure(self._terms_cause)

    def preview_failed(self, detail: str) -> None:
        headline = "The order could not be checked. Try again."
        self._writes.show_result(headline, is_error=True)
        self._notifier.report_failure(
            FailureNotice(
                FailureKind.COMMAND,
                failure_cause(self._venue, "order", "preview"),
                headline,
                detail=detail,
            )
        )

    def submit_failed(self, failure: SubmitFailure) -> str:
        """@return The sentence the panel's line shows."""
        headline = submit_failure_headline(failure, "order")
        self._writes.show_result(headline, is_error=True)
        self._notifier.report_failure(
            submit_failure_notice(
                failure, venue=self._venue, area="order", what="order"
            )
        )
        return headline

    def order_refused(self, text: str) -> None:
        """A domain refusal (the safety gate) is a failure the user must see."""
        self._notifier.report_failure(
            FailureNotice(
                FailureKind.COMMAND,
                failure_cause(self._venue, "order", "refused"),
                text,
            )
        )
