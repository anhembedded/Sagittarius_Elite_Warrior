"""`EPIC-034` D3, D11 — `IRealMoneyConsent`: ask once per mainnet venue per session.

@details Holds only which venues agreed, in memory: nothing persists, so every run
asks again. The question itself is the caller's (`ask`), so this class has no
toolkit in it and is tested with a recorded answer.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_real_money_consent import (
    IRealMoneyConsent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.RealMoney")


@dataclass(frozen=True)
class RealMoneyQuestion:
    venue: TradingVenue
    action: str


type AskRealMoney = Callable[[RealMoneyQuestion], bool]


class RealMoneyConsent(IRealMoneyConsent):
    def __init__(self, ask: AskRealMoney) -> None:
        self._ask = ask
        self._agreed: set[TradingVenue] = set()
        self._lock = threading.Lock()

    def confirmed(self, venue: TradingVenue, action: str) -> bool:
        if not venue.is_mainnet:
            return True
        with self._lock:
            if venue in self._agreed:
                return True
        # Asked outside the lock: the question is a dialog that runs its own
        # event loop, and a second caller must not wait behind it.
        agreed = self._ask(RealMoneyQuestion(venue, action))
        logger.info(
            "Real money on %s for %r: %s [real-money]",
            venue.display_name,
            action,
            "agreed" if agreed else "declined",
        )
        if agreed:
            with self._lock:
                self._agreed.add(venue)
        return agreed
