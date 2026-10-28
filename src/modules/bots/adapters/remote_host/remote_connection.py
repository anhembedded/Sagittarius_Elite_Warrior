"""`EPIC-047E` — the Connect step's one read, answered from what the host published.

@details `GetVenueConnectionQuery` asks a venue's account, terms and symbol rules at one moment, and the screen
locks the chart and the Plan until it is read. The VPS tab reads nothing at the exchange, so the same value is
put together from the host's own reads — the bot's exchange facts (the account), the planner's inputs (fees and
price) and the symbol's rules — and carries the moment the *host* read them (`read_at`), so the screen shows the
account's real age. When one of the three was never published, or the host has no key for the venue, the answer
is the `ConnectFailure` that says so, never a snapshot assembled from defaults.

@par What is not carried
`holdings` is empty: the host publishes the bot's own balances (`ExchangeFacts`), not the account's list of
balances, and nothing in `bots` reads the list (the Connect step reads `available`). Nothing is a stand-in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_reads import (
    BotPlannerRead,
    HostExchangeReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesLoaded,
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    HostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    QUOTE_ASSET,
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: What the failure names as the read that did not happen (`ConnectFailure.detail`).
THE_HOST_FACTS = "the facts the host publishes"
_VENUE_NOT_ENABLED = "the venue is not enabled on the host"


@dataclass(frozen=True, slots=True)
class _Account:
    """What the host's exchange facts say of the account, whichever the venue's kind."""

    available: Decimal
    can_trade: bool | None
    read_at: datetime


def connection_of(
    venue: TradingVenue,
    symbol: str,
    bots: tuple[BotSnapshot, ...],
    held: HostHeldFacts | None,
    reads: HostExchangeReads | None,
) -> VenueAccountSnapshot | ConnectFailure:
    source = AccountSource.for_venue(venue)
    if held is None:
        return _not_published(source)
    refusal = _venue_refusal(source, venue, held)
    if refusal is not None:
        return refusal
    for bot in bots:
        if bot.venue is venue and bot.symbol == symbol:
            built = _snapshot_for(source, bot, held, reads)
            if built is not None:
                return built
    return _not_published(source)


def _venue_refusal(
    source: AccountSource, venue: TradingVenue, held: HostHeldFacts
) -> ConnectFailure | None:
    if venue not in held.enabled_venues:
        return ConnectFailure(
            source, ConnectionFailureKind.NOT_CONFIGURED, _VENUE_NOT_ENABLED
        )
    if not any(key.venue is venue and key.key_saved for key in held.venue_keys):
        return ConnectFailure(source, ConnectionFailureKind.NOT_CONFIGURED)
    return None


def _not_published(source: AccountSource) -> ConnectFailure:
    return ConnectFailure(source, ConnectionFailureKind.NETWORK, THE_HOST_FACTS)


def _snapshot_for(
    source: AccountSource,
    bot: BotSnapshot,
    held: HostHeldFacts,
    reads: HostExchangeReads | None,
) -> VenueAccountSnapshot | None:
    account = _account_of(bot.bot_id, held)
    planner = _planner_of(bot.bot_id, reads)
    rules = _rules_of(bot, reads)
    if account is None or planner is None or rules is None:
        return None
    terms, market = planner.market.terms, planner.market.market
    if terms is None or market is None:
        return None
    return VenueAccountSnapshot(
        source=source,
        symbol=bot.symbol,
        read_at=account.read_at,
        quote_asset=market.quote_asset or QUOTE_ASSET,
        available=account.available,
        holdings=(),
        commission=CommissionRate(bot.symbol, terms.maker_fee, terms.taker_fee),
        can_trade=account.can_trade,
        rules=rules,
        price=market.last_price,
    )


def _account_of(bot_id: str, held: HostHeldFacts) -> _Account | None:
    snapshot = _snapshot_of(bot_id, held)
    if isinstance(snapshot, ExchangeLoaded):
        facts = snapshot.facts
        return _Account(facts.quote_free, facts.can_trade, facts.read_at)
    if isinstance(snapshot, FuturesLoaded):
        futures = snapshot.facts
        return _Account(futures.available_margin, futures.can_trade, futures.read_at)
    return None


def _snapshot_of(bot_id: str, held: HostHeldFacts) -> VenueSnapshot | None:
    return next(
        (read.snapshot for read in held.exchange_reads if read.bot_id == bot_id), None
    )


def _planner_of(bot_id: str, reads: HostExchangeReads | None) -> BotPlannerRead | None:
    if reads is None:
        return None
    return next((read for read in reads.planner if read.bot_id == bot_id), None)


def _rules_of(
    bot: BotSnapshot, reads: HostExchangeReads | None
) -> SymbolOrderMetadata | None:
    if reads is None:
        return None
    return next(
        (
            read.rules
            for read in reads.symbol_rules
            if read.venue is bot.venue and read.symbol == bot.symbol
        ),
        None,
    )
