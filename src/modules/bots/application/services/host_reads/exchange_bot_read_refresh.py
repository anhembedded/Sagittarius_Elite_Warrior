"""`EPIC-047H` — `IBotReadRefresh` over the readers the Bots tab already uses (decision record 2026-10-27, D4).

@details The host reads again, for the VPS tab, what the Bots tab reads from the exchange for a bot:
its facts (`IVenueFacts`), the planner's inputs (`GetPlannerMarketQuery`) and its fills
(`GetBotFillsQuery`), and a venue's static exchange info (`IMarketMetadataProvider.refresh`).
Nothing here is a second reader: each is the query or port the tab dispatches, so a number the tab
shows is the number the Bots tab would have shown.

**Routine, read-only, record-on-success.** Every read goes out at the default `RequestPriority.ROUTINE`, so
it waits at the venue's 70 % line and never takes the exit reserve (`BOT-226`). It does not open a scope of
its own (only the three query handlers do, `test_only_the_query_handlers_open_a_request_priority_scope`);
instead it *refuses* to read inside someone else's scope, which would be the reserve. The facts come from the reader
*beneath* `RecordedVenueFacts` and are recorded here only when they were read: a failed read must
not replace a good snapshot with an `ExchangeUnavailable` (the decision's "a refresh failure leaves
the last snapshot and its `read_at`"). An exchange failure's own words may carry a key or a URL, so
the outcome names the part that failed and the reason stays at DEBUG.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_timeframes import (
    DEFAULT_CHART_TIMEFRAMES,
)
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    GetBotFillsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_fills import BotFills
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_reads import (
    BotFillsRead,
    BotPlannerRead,
    SymbolRulesRead,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_read_refresh import (
    IBotReadRefresh,
    RefreshOutcome,
    RefreshScope,
    RefreshTarget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
    IBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_latest_exchange_reads import (
    ILatestExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_latest_venue_reads import (
    ILatestVenueReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_facts import (
    IVenueFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.request_priority import (
    RequestPriority,
    current_priority,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Bots.HostReads")

_FACTS_NOT_READ = "the exchange's facts were not read"
_PLANNER_NOT_READ = "the planner's inputs were not read"
_FILLS_NOT_READ = "the fills were not read"
_STATIC_NOT_READ = "the exchange info was not read"
_BOT_GONE = "the bot is no longer stored"
_NOT_ROUTINE = "a refresh is made at routine priority only"
_CANDLES_NOT_READ = "the candles were not synced"
_GATE_CLOSED = "the venue's weight gate is closed to routine reads"
#: How many candles of each timeframe a sync reaches back for: a chart's own window, one request of at most 1 000 rows.
CANDLES_BACK = 1000


class ExchangeBotReadRefresh(IBotReadRefresh):
    def __init__(
        self,
        store: IBotStore,
        facts: IVenueFacts,
        dispatcher: ICommandDispatcher,
        contexts: IVenueContexts,
        clock: IBotClock,
        venue_reads: ILatestVenueReads,
        exchange_reads: ILatestExchangeReads,
        market_data: IMarketDataSources,
    ) -> None:
        self._store = store
        self._facts = facts
        self._dispatcher = dispatcher
        self._contexts = contexts
        self._clock = clock
        self._venue_reads = venue_reads
        self._exchange_reads = exchange_reads
        self._market_data = market_data

    def targets(self) -> tuple[RefreshTarget, ...]:
        stored = self._store.load_all().bots
        self._exchange_reads.retain([item.bot.bot_id.value for item in stored])
        enabled = self._contexts.enabled()
        return tuple(
            RefreshTarget(
                item.bot.bot_id.value,
                item.bot.definition.venue,
                item.bot.definition.symbol,
                exposure=item.bot.state not in RUN_STARTING_STATES,
            )
            for item in sorted(stored, key=lambda item: item.bot.bot_id.value)
            if item.bot.definition.venue in enabled
        )

    def refresh(self, bot_id: str, scope: RefreshScope) -> RefreshOutcome:
        try:
            bot = self._store.load(BotId(bot_id)).bot
        except BotNotFoundError:
            return RefreshOutcome(None, _BOT_GONE)
        if current_priority() is not RequestPriority.ROUTINE:
            return RefreshOutcome(None, _NOT_ROUTINE)
        if scope is RefreshScope.FACTS:
            return self._read_facts(bot)
        if scope is RefreshScope.PLANNER:
            return self._read_planner(bot)
        if scope is RefreshScope.CANDLES:
            return self._sync_candles(bot)
        return self._read_fills(bot)

    def refresh_static(self, venue: TradingVenue) -> RefreshOutcome:
        if current_priority() is not RequestPriority.ROUTINE:
            return RefreshOutcome(None, _NOT_ROUTINE)
        symbols = sorted(
            {
                item.bot.definition.symbol
                for item in self._store.load_all().bots
                if item.bot.definition.venue is venue
            }
        )
        try:
            provider = self._contexts.get(venue).metadata_provider
            provider.refresh()
            read_at = self._clock.now()
            for symbol in symbols:
                rules = provider.get_or_fetch(symbol)
                if rules is not None:
                    self._exchange_reads.record_rules(
                        SymbolRulesRead(venue, symbol, read_at, rules)
                    )
        except Exception as failure:  # noqa: BLE001 - the seam to the exchange: any failed read is a word, never a thrown error
            logger.debug("static info of %s not read: %s", venue.value, failure)
            return RefreshOutcome(None, _STATIC_NOT_READ)
        return RefreshOutcome(read_at)

    def _read_facts(self, bot: Bot) -> RefreshOutcome:
        snapshot = self._facts.read(bot)
        if not isinstance(snapshot, ExchangeLoaded | FuturesLoaded):
            logger.debug("Bot %s: facts not read: %s", bot.bot_id.value, snapshot)
            return RefreshOutcome(None, _FACTS_NOT_READ)
        self._venue_reads.record(bot.bot_id.value, snapshot)
        return RefreshOutcome(snapshot.facts.read_at)

    def _sync_candles(self, bot: Bot) -> RefreshOutcome:
        """Bring the store's candles of the bot's symbol up to now, one sync per timeframe the chart pins.
        The sync is `market_data`'s own use case, the one the Bots tab's chart runs on a desktop."""
        definition = bot.definition
        market = definition.venue.market_type
        if market is None:
            return RefreshOutcome(None, _CANDLES_NOT_READ)
        meter = self._contexts.get(definition.venue).weight_meter
        if meter is not None and not meter.read().routine_open:
            # the sync rides `market_data`'s own client, outside `ExchangeCallPolicy`: the gate is asked here
            return RefreshOutcome(None, _GATE_CLOSED)
        sync = self._market_data.ports_for(definition.venue.market_data_venue).sync
        now = self._clock.now()
        try:
            for code in DEFAULT_CHART_TIMEFRAMES:
                timeframe = TimeFrame(code)
                sync.sync(
                    MarketDataSyncRequest(
                        symbols=(definition.symbol,),
                        interval=timeframe,
                        market=market,
                        start_time=now
                        - timedelta(seconds=CANDLES_BACK * timeframe.to_seconds()),
                    )
                )
        except Exception as failure:  # noqa: BLE001 - the seam to the exchange: any failed sync is a word, never a thrown error
            logger.debug("Bot %s: candles not synced: %s", bot.bot_id.value, failure)
            return RefreshOutcome(None, _CANDLES_NOT_READ)
        return RefreshOutcome(now)

    def _read_planner(self, bot: Bot) -> RefreshOutcome:
        definition = bot.definition
        try:
            market = self._dispatcher.dispatch(
                GetPlannerMarketQuery,
                GetPlannerMarketQuery(definition.venue, definition.symbol),
            )
        except Exception as failure:  # noqa: BLE001 - the seam to the exchange: any failed read is a word, never a thrown error
            logger.debug("Bot %s: planner not read: %s", bot.bot_id.value, failure)
            return RefreshOutcome(None, _PLANNER_NOT_READ)
        if not isinstance(market, PlannerMarket) or market.problem:
            return RefreshOutcome(None, _PLANNER_NOT_READ)
        read_at = self._clock.now()
        self._exchange_reads.record_planner(
            BotPlannerRead(bot.bot_id.value, read_at, market)
        )
        return RefreshOutcome(read_at)

    def _read_fills(self, bot: Bot) -> RefreshOutcome:
        try:
            fills = self._dispatcher.dispatch(
                GetBotFillsQuery, GetBotFillsQuery(bot.bot_id.value)
            )
        except Exception as failure:  # noqa: BLE001 - the seam to the exchange: any failed read is a word, never a thrown error
            logger.debug("Bot %s: fills not read: %s", bot.bot_id.value, failure)
            return RefreshOutcome(None, _FILLS_NOT_READ)
        if not isinstance(fills, BotFills) or fills.problem or fills.refused:
            return RefreshOutcome(None, _FILLS_NOT_READ)
        read_at = self._clock.now()
        self._exchange_reads.record_fills(
            BotFillsRead(bot.bot_id.value, read_at, fills)
        )
        return RefreshOutcome(read_at)
