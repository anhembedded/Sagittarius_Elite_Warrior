"""`EPIC-039G` — a Futures account was charged, or paid, a funding fee."""

from dataclasses import dataclass, field
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class FundingChargedEvent(BaseEvent):
    """
    @brief Domain event fired when the exchange settles a funding fee on `symbol`
    (`ACCOUNT_UPDATE` with reason `FUNDING_FEE`).

    @details `amount` is the wallet's change in the quote asset, signed: negative is
    paid, positive is earned. Funding is a wallet event, not a fill, so it travels on
    its own event; counting it with the fills would hide a losing grid behind a
    funding gain. Not `frozen`, the same `BaseEvent` inheritance cost
    `OrderFilledEvent` documents; read-only by convention.
    """

    symbol: str
    amount: Decimal
    venue: TradingVenue = field(kw_only=True)
