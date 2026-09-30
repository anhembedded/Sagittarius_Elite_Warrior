"""`EPIC-028D` — keeps a venue's account summary current: on the account
refresh cadence, and straight after every fill on that venue.

@details Same shape as `HoldingsRefreshService` (re-read through a query,
republish on the bus, no-op while the venue's trading is off), with two
differences.

**Publishes only on change.** The summary is re-read every few seconds and
is usually the same; republishing an identical summary each time would
repaint every screen showing it for nothing.

**A fill asks for a refresh, it does not perform one.** `OrderFilledEvent`
arrives on the thread of the user-data stream that received it, an asyncio
loop (`BOT-145`: no REST call may block that loop). `on_order_filled` hands
`refresh_once` to `run_elsewhere`, which the composition root points at a
worker pool, so the account read after a fill never stalls the stream.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_account_summary import (
    GetAccountSummaryQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.account_summary_changed_event import (
    AccountSummaryChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.AccountSummaryRefresh")

#: Runs a callable off the caller's thread; returns whatever handle the
#: runner gives (a `Future`, say), which this service ignores.
RunElsewhere = Callable[[Callable[[], None]], object]


@dataclass(frozen=True)
class AccountSummaryRefreshPorts:
    """What every venue's summary refresh shares: where it reads, where it
    publishes, and where it runs a refresh asked for by a fill."""

    dispatcher: ICommandDispatcher
    event_publisher: IEventPublisher
    run_elsewhere: RunElsewhere


class AccountSummaryRefreshService:
    """@brief Re-reads one venue's account summary and republishes it
    through `AccountSummaryChangedEvent` when it changed."""

    def __init__(
        self,
        ports: AccountSummaryRefreshPorts,
        session_state: TradingSessionState,
        venue: TradingVenue,
    ) -> None:
        self._ports = ports
        self._session_state = session_state
        self._venue = venue
        self._last_published: AccountSummary | None = None

    @property
    def venue(self) -> TradingVenue:
        """The one venue this service reads and republishes."""
        return self._venue

    def refresh_once(self) -> None:
        if not self._session_state.enabled:
            return

        try:
            summary = cast(
                AccountSummary | None,
                self._ports.dispatcher.dispatch(
                    GetAccountSummaryQuery, GetAccountSummaryQuery(venue=self._venue)
                ),
            )
        except Exception as exc:  # noqa: BLE001 - worker boundary: a transient network hiccup must not kill the scheduler's job thread; the next tick tries again
            logger.debug(
                "Account summary refresh failed on %s: %s", self._venue.value, exc
            )
            return

        if summary is None or summary == self._last_published:
            return
        self._last_published = summary
        self._ports.event_publisher.publish(AccountSummaryChangedEvent(summary=summary))

    def on_order_filled(self, event: OrderFilledEvent) -> None:
        """A fill on this venue changes its balances now, not at the next
        tick; another venue's fill changes nothing here."""
        if event.venue is self._venue:
            self._ports.run_elsewhere(self.refresh_once)
