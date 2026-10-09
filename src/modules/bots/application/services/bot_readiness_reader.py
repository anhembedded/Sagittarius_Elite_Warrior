"""`EPIC-034H` — reads the world a bot starts into, and asks `assess_readiness`.

The Start use case and `GetBotReadinessQuery` both come here, so a start is
refused for exactly what the query reports. It reads afresh what the Bots
screen holds from earlier (the account, the market numbers) and what only the
server knows (every other bot, who holds the symbol), then hands them to the
same assessment the screen calls with what it holds.

Nothing here places an order, claims a lease or registers a budget: those are
Start's own steps, after this answered "nothing left".
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.account_view import (
    account_view_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_run_facts import (
    BotRunFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.connect_failure_words import (
    failure_state,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exchange_facts_reader import (
    ExchangeFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.other_active_bot import (
    other_active_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.planner_numbers import (
    read_planner_numbers,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness_assessment import (
    ConnectionRead,
    ConnectionState,
    ReadinessInputs,
    assess_readiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
    UnknownAccountSourceError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

logger = logging.getLogger("App.Bots.Readiness")


class BotReadinessReader:
    """@brief What is left before `bot` may start, from the world as it is now."""

    def __init__(
        self,
        store: IBotStore,
        kinds: IBotKindCatalog,
        accounts: IVenueAccounts,
        ports: IVenueTradingPorts,
        caps: OwnerBudgetCaps,
        exchange: ExchangeFactsReader,
    ) -> None:
        self._store = store
        self._kinds = kinds
        self._accounts = accounts
        self._ports = ports
        self._caps = caps
        self._exchange = exchange
        self._run_facts = BotRunFactsReader(ports, caps)

    def read(self, bot: Bot, config: Mapping[str, str] | None = None) -> BotReadiness:
        definition = bot.definition
        judged = dict(config) if config is not None else dict(definition.config)
        bot_id = bot.bot_id.value
        answer = self._account(bot)
        connection, account_ok = self._connection(bot, answer)
        readings = self._store.load_all()
        run = self._run_facts.read(
            bot_id,
            definition.venue,
            definition.symbol,
            judged,
            other_active_bot(
                bot_id,
                ((s.bot.bot_id.value, s.bot.state) for s in readings.bots),
                (refused.name for refused in readings.refused),
            ),
        )
        readiness = assess_readiness(
            ReadinessInputs(
                kind=self._kind(definition.kind),
                kind_id=definition.kind,
                symbol=definition.symbol,
                config=judged,
                connection=connection,
                market=self._market(bot) if account_ok else None,
                run=run,
                exchange=self._exchange.read(bot),
            )
        )
        logger.debug(
            "Bot %s readiness: %d thing(s) left (%s)",
            bot_id,
            readiness.things_left,
            ", ".join(item.code for item in readiness.items) or "none",
        )
        return readiness

    def _kind(self, kind_id: str) -> IBotKind | None:
        try:
            return self._kinds.kind(kind_id)
        except UnknownBotKindError:
            return None

    def _account(self, bot: Bot) -> VenueAccountSnapshot | ConnectFailure:
        source = AccountSource.for_venue(bot.definition.venue)
        try:
            return self._accounts.reader(source).read(bot.definition.symbol)
        except UnknownAccountSourceError:
            return ConnectFailure(
                source, ConnectionFailureKind.NOT_CONFIGURED, "the venue is not enabled"
            )

    def _connection(
        self, bot: Bot, answer: VenueAccountSnapshot | ConnectFailure
    ) -> tuple[ConnectionRead, bool]:
        title = AccountSource.for_venue(bot.definition.venue).venue_title
        if isinstance(answer, VenueAccountSnapshot):
            return (
                ConnectionRead(
                    ConnectionState.CONNECTED, title, account_view_of(answer)
                ),
                True,
            )
        return (
            ConnectionRead(ConnectionState.FAILED, title, reason=failure_state(answer)),
            False,
        )

    def _market(self, bot: Bot) -> PlannerMarket:
        numbers = read_planner_numbers(
            self._ports, self._caps, bot.definition.venue, bot.definition.symbol
        )
        if isinstance(numbers, str):
            return PlannerMarket(None, None, None, None, numbers)
        terms, view = numbers
        return PlannerMarket(terms, view, None, None)
