from dataclasses import dataclass

from Binace_Bot.src.domain.entities.market_data import MarketData


@dataclass(frozen=True)
class MarketTickEvent:
    """
    Event fired when a new market tick (kline update) is received from the live stream.
    """

    market_data: MarketData
