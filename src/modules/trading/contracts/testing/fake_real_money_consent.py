"""`EPIC-034` D3, D11 — the verified fake for `IRealMoneyConsent`.

@details Answers what a test says (agreeing by default) and records every
question it was asked, as the real one is asked once per mainnet venue per session:
a test of the real class is `tests/unit/modules/trading/application/
test_real_money_consent.py`. A testnet venue is never asked here either.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_real_money_consent import (
    IRealMoneyConsent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class FakeRealMoneyConsent(IRealMoneyConsent):
    def __init__(self, agrees: bool = True) -> None:
        self.agrees = agrees
        #: `(venue, action)` of each question asked, in order.
        self.asked: list[tuple[TradingVenue, str]] = []

    def confirmed(self, venue: TradingVenue, action: str) -> bool:
        if not venue.is_mainnet:
            return True
        self.asked.append((venue, action))
        return self.agrees
