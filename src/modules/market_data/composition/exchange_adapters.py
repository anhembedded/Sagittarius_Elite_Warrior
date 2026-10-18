"""The two market-data adapters that import the exchange SDK, named by import path (`PRO-014`).

`python-binance` costs about 0.4 s to import (`dateparser`, `aiohttp`, `requests` and
`pycryptodome` come with it), and a run that never reaches the exchange - `bot list` reads
a file - should not pay it. Importing `binance_websocket_service` or
`market_data_session_factory` at the top of a composition file made every run pay at boot;
these two functions import the class at the first call, which is the first time a stream is
opened or a client is built. `bind_adapters` and `MarketDataVenues` are the only callers.

A separate file from `adapter_bindings.py`: two registries (`MarketDataVenues`, the bindings)
need the same two paths, and a path written twice is two paths to keep right.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_session_factory import (
    IExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_live_stream_service import (
    ILiveStreamService,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager

_ADAPTERS = "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance"

_LIVE_STREAM_SERVICE: Deferred[ILiveStreamService] = Deferred(
    f"{_ADAPTERS}.binance_websocket_service:BinanceWebsocketService"
)
_SESSION_FACTORY: Deferred[IExchangeSessionFactory] = Deferred(
    f"{_ADAPTERS}.market_data_session_factory:MarketDataSessionFactory"
)


def new_live_stream_service(
    event_bus: IEventBus, tasks: ITaskManager, venue: MarketDataVenue
) -> ILiveStreamService:
    """A `BinanceWebsocketService` for `venue`; the SDK is imported by this call."""
    return _LIVE_STREAM_SERVICE(event_bus, tasks, venue)


def new_session_factory(venue: MarketDataVenue) -> IExchangeSessionFactory:
    """A `MarketDataSessionFactory` for `venue`; the SDK is imported by this call."""
    return _SESSION_FACTORY(venue)
