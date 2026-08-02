from dataclasses import dataclass
from sagittarius_engine.domain.base_event import BaseEvent
from Binace_Bot.src.domain.entities.market_data import MarketData


@dataclass(frozen=True)
class MarketTickEvent(BaseEvent):
    """
    Event fired when a new market tick (kline update) is received from the live stream.
    """

    market_data: MarketData
