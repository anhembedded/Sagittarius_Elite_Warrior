from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class MarketTickEvent(BaseEvent):
    """
    Event fired when a new market tick (kline update) is received from the live stream.

    @par Not `frozen` — a cost of inheriting `BaseEvent` (`EPIC-008F`)
    This was `@dataclass(frozen=True)`. Python forbids a frozen dataclass from
    inheriting a non-frozen one, and `BaseEvent` cannot become frozen: it
    supports subclasses with hand-written `__init__` that assign attributes
    (the engine's own `HealthUpdatedEvent` is one), which freezing would break.
    So adopting the Shared Kernel base costs immutability here.

    Not free: `test_signal_generated_event_is_no_longer_frozen` used to assert
    `FrozenInstanceError` here, so this trades away a guarantee somebody had
    deliberately locked down. User chose to accept that (2026-08-25) rather
    than give up registry membership. Treat these as read-only **by
    convention** now — a handler that mutates an event mutates it for every
    later subscriber in the same fan-out, and nothing stops it any more.

    Equality still works on payload: `BaseEvent` marks its `_event_id` /
    `_occurred_on` `compare=False`, without which a per-instance UUID would
    make two identical events compare unequal.

    @par `market_type` (`EPIC-028C`)
    Which market's stream the candle came from. `BTCUSDT` is two different
    instruments on Spot and on USD-M Futures, with two different prices, so a
    consumer filters on this before trusting the candle: a Spot kline must
    never drive a Futures strategy or chart. Keyword-only with no default —
    a producer that forgets it is a `TypeError`, never a candle silently
    labelled Spot.

    @par `market_data_venue` (`BUG-172`)
    Which environment's stream the candle came from. Spot Testnet's `BTCUSDT`
    and Spot Mainnet's are two series with two prices, and every venue now
    streams its own, so a consumer keeps only the candles of the venue it acts
    on (`TradingVenue.market_data_venue`): a testnet candle must never drive a
    mainnet strategy, bot or chart. Keyword-only with no default, for the reason
    `market_type` has none.
    """

    market_data: MarketData
    market_type: MarketType = field(kw_only=True)
    market_data_venue: MarketDataVenue = field(kw_only=True)
