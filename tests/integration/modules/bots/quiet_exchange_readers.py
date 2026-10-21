"""`BUG-249` - a journey about what one request meets asks the exchange from one reader only.

@details Several readers of the composed app ask the exchange on their own, on the real clock or on
a worker thread, and a journey that queues an answer for the next matching request (a 429 on
`/ping`, a count of `positionRisk` reads) meets whichever of them asks first:

- the trading module's refresh jobs (positions, holdings and the account summary), every
  `trading.position_refresh_interval_seconds` of real time;
- the account summary a fill asks for on the worker pool, racing the bot's own order for the
  answer queued for the connection check;
- the connection check an order trusts for `ORDER_CONNECTION_REUSE_SECONDS` of real time
  (`BUG-247`), so an order inside that window does not ask at all.

The journeys below are about the bots' own requests, so these three are stood down first. A fast
runner and a slow one then see the same sequence.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.application.account_summary_refresh_service import (
    AccountSummaryRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.holdings_refresh_service import (
    HoldingsRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.position_refresh_service import (
    PositionRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces import IEventBus
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.runtime.scheduler.scheduler import Scheduler

_REFRESHES = (
    PositionRefreshService,
    HoldingsRefreshService,
    AccountSummaryRefreshService,
)


def quiet_the_trading_refreshes(container: IContainer) -> None:
    """The trading module's periodic refreshes stop, and a fill no longer asks for an account
    summary; what the bots send is then all the exchange hears from the app."""
    for job in tuple(container.resolve(Scheduler).jobs):
        if isinstance(getattr(job.fn, "__self__", None), _REFRESHES):
            job.cancel()
    bus = container.resolve(IEventBus)
    for handler in bus.get_handlers(OrderFilledEvent):
        if isinstance(getattr(handler, "__self__", None), AccountSummaryRefreshService):
            bus.off(OrderFilledEvent, handler)


def forget_the_kept_connection(container: IContainer, venue: TradingVenue) -> None:
    """The next order on `venue` asks the exchange whether the connection works."""
    container.resolve(VenueTradingScopes).get(venue).order_connection.forget()
