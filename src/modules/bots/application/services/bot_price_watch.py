"""`EPIC-035A` — every bot that is not at rest owns its price stream.

Stop loss and take profit act on `MarketTickEvent`s, and a tick exists only
while someone streams the symbol. Until this service the only streamer was the
selected bot's chart, so closing the chart, selecting another bot or restarting
the app left a crossed stop unnoticed. A safety rule must not depend on a widget
being open (`EPIC-035A` §3): the bot owns its stream.

@par What it does
  · **Owns a stream per bot** through market data's `IMarketStream` (never the
    Binance adapter), on the bot's own venue and Spot market, under its own owner
    id (`bot_price_owner`), from the moment the bot leaves DRAFT or STOPPED until
    it returns to one. The venue's `ILiveStreamService` counts owners per
    symbol, so two bots on one symbol share one subscription and the last to
    leave releases it.
  · **Follows the bot's state, not its executor.** It listens to
    `BotChangedEvent` (the store publishes one per write, so every state change
    of every writer passes it) and reads the bot back from the store: the store
    is the truth, an event only says "look again".
  · **Makes sure a watched bot has an executor** that can hear its ticks: at
    start-up for every restored bot, and on every check for a bot whose venue was
    not enabled yet (the executor needs the venue's trading ports).
  · **Asks every executor, every `CHECK_EVERY_SECONDS`, whether its feed went
    quiet** (`GridExecutor.on_price_age_check`), and starts again a stream that
    refused to open. The staleness HALT itself is the executor's, posted on its
    own queue like every other task.

@par Extension cases
  · Futures grid (`EPIC-029K`): the market type comes from the bot's venue; one
    more `MarketType` is no change here;
  · a second kind of bot: it owns a stream the same way; the kind-specific part
    is its executor's `on_price_age_check`.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
    IBotStore,
    UnreadableBotError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_ticker import (
    IBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    PRICE_STREAM_STATES,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Bots.PriceWatch")

#: How often every bot is asked whether its feed went quiet. Small beside
#: `PRICE_STALE_AFTER_SECONDS`, so a halt is at most this late.
CHECK_EVERY_SECONDS: float = 5.0

#: Kline updates arrive about every two seconds at any interval while the pair
#: trades; the shortest interval keeps the cadence the staleness limits assume.
_STREAM_INTERVAL = TimeFrame.ONE_MINUTE


def bot_price_owner(bot_id: BotId) -> str:
    """@brief A bot's own owner on the market stream for its price (`EPIC-035A`):
    `bot-price.<id>`. Not the chart's `bot.<id>`: a stream owner's start
    *replaces* its subscription set (`BOT-126`), so two screens sharing one owner
    would fight over it."""
    return f"bot-price.{bot_id}"


@dataclass(frozen=True, slots=True)
class _Watched:
    """What one watched bot streams, and whether its stream is open."""

    venue: TradingVenue
    symbol: str
    stream: IMarketStream
    open: bool


class BotPriceWatch:
    """Keeps one price stream per bot that is not at rest."""

    def __init__(
        self,
        store: IBotStore,
        sources: IMarketDataSources,
        executors: BotExecutors,
        ticker: IBotTicker,
    ) -> None:
        self._store = store
        self._sources = sources
        self._executors = executors
        self._ticker = ticker
        self._lock = threading.RLock()
        self._watched: dict[str, _Watched] = {}
        #: Bots whose executor could not be built, so the error is said once.
        self._unbuildable: set[str] = set()
        self._closed = False

    def start(self) -> None:
        """Watch every stored bot that is not at rest, then tick."""
        for stored in self._store.load_all().bots:
            self._reconcile(stored.bot.bot_id.value)
        self._ticker.every(CHECK_EVERY_SECONDS, self._check)
        logger.info("Bot price watch started: %d bot(s)", len(self._watched))

    def on_bot_changed(self, event: BotChangedEvent) -> None:
        """A bot was saved or deleted: look at it again."""
        if event.removed:
            self._release(event.bot_id)
        else:
            self._reconcile(event.bot_id)

    def close(self) -> None:
        """Release every stream and stop ticking. Safe to call twice."""
        with self._lock:
            self._closed = True
            bot_ids = tuple(self._watched)
        for bot_id in bot_ids:
            self._release(bot_id)
        self._ticker.close()

    # --- which bots are watched ---

    def _reconcile(self, bot_id: str) -> None:
        """Make the bot's stream match its stored state.

        The read of the store and the change of the stream are one step under the
        lock: handlers run on whichever thread saved the bot, and a snapshot read
        before another thread's release must not reopen a stream after it, nor a
        release run after another thread's open (the owner id is the bot's, so a
        late stop would close the new stream)."""
        with self._lock:
            if self._closed:
                return
            try:
                bot = self._store.load(BotId(bot_id)).bot
            except (BotNotFoundError, UnreadableBotError):
                self._release(bot_id)
                return
            if bot.state not in PRICE_STREAM_STATES:
                self._release(bot_id)
                return
            self._hold(bot)
        self._ensure_executor(bot)

    def _hold(self, bot: Bot) -> None:
        """Open the bot's stream unless it is open. The caller holds the lock."""
        bot_id = bot.bot_id.value
        held = self._watched.get(bot_id)
        if self._closed or (held is not None and held.open):
            return
        market = bot.definition.venue.market_type
        if market is None:
            logger.warning(
                "Bot %s: its venue %s trades no market; no price stream",
                bot_id,
                bot.definition.venue.value,
            )
            return
        self._watched[bot_id] = self._open(bot, market)

    def _open(self, bot: Bot, market: MarketType) -> _Watched:
        definition = bot.definition
        venue = definition.venue
        stream = self._sources.ports_for(venue.market_data_venue).stream
        outcome = stream.start(
            bot_price_owner(bot.bot_id), market, [definition.symbol], _STREAM_INTERVAL
        )
        if not outcome.success:
            logger.warning(
                "Bot %s: its %s price stream did not open (%s); trying again at the "
                "next check",
                bot.bot_id,
                definition.symbol,
                outcome.message,
            )
        else:
            logger.info(
                "Bot %s: owns its %s price stream on %s",
                bot.bot_id,
                definition.symbol,
                venue.value,
            )
        return _Watched(venue, definition.symbol, stream, outcome.success)

    def _release(self, bot_id: str) -> None:
        """Stop the bot's stream, under the lock: see `_reconcile`."""
        with self._lock:
            held = self._watched.pop(bot_id, None)
            if held is None:
                return
            held.stream.stop(bot_price_owner(BotId(bot_id)))
        logger.info("Bot %s: released its %s price stream", bot_id, held.symbol)

    def _ensure_executor(self, bot: Bot) -> None:
        """A bot with no executor hears no tick. The factory needs the venue's
        trading ports, which exist once trading on that venue is enabled; until
        then there is nothing to build and the next check tries again.

        Never for a STARTING bot: a bot is STARTING with no executor only while
        `BotRunner.start` is between saving it and building its executor
        (`fresh`), and a second executor built here would be a second writer for
        the bot. A restored STARTING bot is HALTED by the restart rule."""
        bot_id = bot.bot_id.value
        if bot.state is BotLifecycleState.STARTING:
            return
        if self._executors.get(bot_id) is not None:
            return
        try:
            self._executors.for_bot(bot)
        except VenueNotEnabledError:
            logger.info(
                "Bot %s: no executor yet, trading on %s is not enabled",
                bot_id,
                bot.definition.venue.value,
            )
        except (ValueError, LookupError):
            # A stored bot the factory cannot read (a ladder or parameters it
            # refuses) must not stop the others from being watched; it is said
            # once, with its traceback, not every check.
            if bot_id not in self._unbuildable:
                self._unbuildable.add(bot_id)
                logger.exception("Bot %s: no executor could be built for it", bot_id)
        else:
            self._unbuildable.discard(bot_id)

    # --- every few seconds ---

    def _check(self) -> None:
        with self._lock:
            bot_ids = tuple(self._watched)
        for bot_id in bot_ids:
            self._check_one(bot_id)

    def _check_one(self, bot_id: str) -> None:
        self._reconcile(bot_id)
        executor = self._executors.get(bot_id)
        if executor is not None:
            executor.facts.on_price_age_check()
