"""`EPIC-035I` — after a wake, each bot's stop loss and take profit meet a fresh price.

The price a bot last heard is the one the sleep froze, and its stream died with
the connection. So the price is read from the venue (`IFreshPriceReader`), once
per symbol, and given to each bot as a tick: the same `on_tick` a streamed price
takes, so the exit rules are the ones a live bot has and nothing is duplicated.

The network is often not back at the instant the machine wakes, so a read that
fails is tried again every `price_retry_every`, `price_attempts` times in all.
Past that the bot is left to the staleness rule (`EPIC-035A`), which halts a bot
whose feed stays quiet. A newer wake supersedes a chain still retrying.
"""

from __future__ import annotations

import logging
import threading
from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    FreshPriceUnavailableError,
    IFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Bots.Sleep")

_Market = tuple[TradingVenue, str]


class WakeExitCheck:
    """Reads a fresh price per symbol and hands it to the bots that trade it."""

    def __init__(
        self,
        executors: BotExecutors,
        prices: IFreshPriceReader,
        retries: IBotRetryScheduler,
        attempts: tuple[int, timedelta],
    ) -> None:
        self._executors = executors
        self._prices = prices
        self._retries = retries
        self._attempts, self._retry_every = attempts
        self._lock = threading.Lock()
        self._generation = 0

    def begin(self) -> None:
        """A wake: check every market the bots trade, superseding an older chain."""
        with self._lock:
            self._generation += 1
            generation = self._generation
        self._attempt(self._markets(), 1, generation)

    def _markets(self) -> set[_Market]:
        return {(e.venue, e.symbol) for e in self._executors.all()}

    def _attempt(self, markets: set[_Market], number: int, generation: int) -> None:
        with self._lock:
            if generation != self._generation:
                return
        unread = {market for market in markets if not self._check(market)}
        if not unread:
            return
        if number >= self._attempts:
            logger.warning(
                "No fresh price after %d tries for %s; the price-feed staleness "
                "rule takes over [sleep-price-gave-up]",
                number,
                sorted(f"{venue.value} {symbol}" for venue, symbol in unread),
            )
            return
        self._retries.after(
            self._retry_every, lambda: self._attempt(unread, number + 1, generation)
        )

    def _check(self, market: _Market) -> bool:
        """Read `market`'s price and tick its bots; `False` when it was unreadable."""
        venue, symbol = market
        try:
            price = self._prices.read(venue, symbol)
        except FreshPriceUnavailableError as exc:
            logger.info(
                "Fresh price of %s %s unavailable: %s", venue.value, symbol, exc
            )
            return False
        self._tick(market, price)
        return True

    def _tick(self, market: _Market, price: Decimal) -> None:
        venue, symbol = market
        for executor in self._executors.on_venue(venue):
            if executor.symbol == symbol:
                executor.facts.on_tick(PriceTick.at(price))
        logger.info(
            "Fresh price of %s %s is %s; stop loss and take profit checked "
            "[sleep-exit-check]",
            venue.value,
            symbol,
            price,
        )
