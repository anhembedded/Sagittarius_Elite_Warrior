"""`BUG-249` - a journey about what one request meets asks the exchange from one reader only.

@details Several readers of the composed app ask the exchange on their own, on the real clock or on
a worker thread, and a journey that queues an answer for the next matching request (a 429 on
`/ping`, a count of `positionRisk` reads) meets whichever of them asks first:

- the trading module's refresh jobs (positions, holdings and the account summary), every
  `trading.position_refresh_interval_seconds` of real time: `NO_PERIODIC_REFRESH` as the world's
  configuration puts the first run beyond any journey, so no job starts and none is cancelled;
- the account summary a fill asks for on the worker pool, racing the bot's own order for the
  answer queued for the connection check: `quiet_the_fill_summaries`;
- the connection check an order trusts for `ORDER_CONNECTION_REUSE_SECONDS` of real time
  (`BUG-247`), so an order inside that window does not ask at all: `forget_the_kept_connection`.

The journeys below are about the bots' own requests, so these three are stood down first. A fast
runner and a slow one then see the same sequence.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.application.account_summary_refresh_service import (
    AccountSummaryRefreshService,
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

#: Far beyond any journey, so the trading module's refreshes never run (`next_run` is now plus
#: the interval); pass it as the world's configuration.
NO_PERIODIC_REFRESH = {"trading.position_refresh_interval_seconds": 3600}


def quiet_the_fill_summaries(container: IContainer) -> None:
    """A fill no longer asks for an account summary; what the bots send is then all the exchange
    hears from the app. Fails when none was found, so a renamed service or a wrapped handler
    cannot turn this into a silent no-op."""
    bus = container.resolve(IEventBus)
    summaries = [
        handler
        for handler in bus.get_handlers(OrderFilledEvent)
        if isinstance(getattr(handler, "__self__", None), AccountSummaryRefreshService)
    ]
    assert summaries, "no fill handler of an account summary refresh is subscribed"
    for handler in summaries:
        bus.off(OrderFilledEvent, handler)


def forget_the_kept_connection(container: IContainer, venue: TradingVenue) -> None:
    """The next order on `venue` asks the exchange whether the connection works."""
    container.resolve(VenueTradingScopes).get(venue).order_connection.forget()
