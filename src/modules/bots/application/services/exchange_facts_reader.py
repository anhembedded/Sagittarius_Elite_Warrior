"""`BOT-173` — reads the exchange's facts about one bot's symbol and account.

@details The one place the venue is asked for what readiness needs: the account's
free and locked balances of the symbol's base and quote, the orders resting on the
symbol (the bot's own apart from the rest), and what the bot's earlier runs left.
It answers an `ExchangeSnapshot` and never raises: a read that failed is
`ExchangeUnavailable` with the reason in words, so a rule can never mistake a
failed read for an empty account.

It is called off the UI thread by `GetExchangeFactsQueryHandler` (the screen's
load, refreshed on demand and when the bot's state changes) and at the click by
`BotReadinessReader` (Start) and `ResumeReadinessReader` (Resume): the same reads,
the same snapshot, judged by the same rules.

Every read is read-only, through the venue's trading ports (the account's own
check, the open orders, the session's history read), so it adds no read of the
Connect step's account snapshot: the Connect step and this one stay two reads of
two different things.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.connect_failure_words import (
    failure_state,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeFacts,
    ExchangeLoaded,
    ExchangeSnapshot,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsInventory,
    EarlierRunsRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

logger = logging.getLogger("App.Bots.Readiness")

_ZERO = Decimal(0)


class ExchangeFactsReader:
    """@brief What the exchange says about `bot`'s symbol and account, now."""

    def __init__(self, ports: IVenueTradingPorts, clock: IBotClock) -> None:
        self._ports = ports
        self._clock = clock

    def read(self, bot: Bot) -> ExchangeSnapshot:
        definition = bot.definition
        try:
            ports = self._ports.get(definition.venue)
        except VenueNotEnabledError:
            return self._unavailable(
                bot, f"{definition.venue.display_name} is not enabled"
            )
        status = ports.account_snapshot.check_connection()
        if status.failure is not None or not status.reachable:
            return self._unavailable(bot, _failure_words(bot, status))
        if status.holdings is None or _available_of(status) is None:
            return self._unavailable(bot, "the account's balances were not read")
        try:
            orders = ports.account_activity.open_orders()
        except Exception as exc:  # noqa: BLE001 - converted at the seam: any failed read (network, rate limit, key) is an unavailable snapshot, never a thrown error and never an empty list
            logger.debug("Open orders of %s not read: %s", definition.symbol, exc)
            return self._unavailable(bot, f"the open orders were not read ({exc})")
        base = definition.symbol.removesuffix(BUDGET_QUOTE_ASSET)
        earlier = ports.trading_session.earlier_runs_inventory(
            EarlierRunsRequest(
                tag=bot.bot_id.value,
                symbol=definition.symbol,
                base_asset=base,
                since=bot.created_at,
                until=self._clock.now(),
            )
        )
        return ExchangeLoaded(_facts(bot, status, orders, earlier, self._clock.now()))

    def _unavailable(self, bot: Bot, reason: str) -> ExchangeUnavailable:
        logger.info(
            "Bot %s: the exchange's facts are unavailable: %s [exchange-facts]",
            bot.bot_id.value,
            reason,
        )
        return ExchangeUnavailable(reason)


def _failure_words(bot: Bot, status: ExchangeConnectionStatus) -> str:
    source = AccountSource.for_venue(bot.definition.venue)
    kind = status.failure or ConnectionFailureKind.NETWORK
    return failure_state(ConnectFailure(source, kind, "the account"))


def _available_of(status: ExchangeConnectionStatus) -> Decimal | None:
    """What a new order can spend in the quote asset, as the Connect step
    reads it (`composed_venue_account_reader`)."""
    summary = status.summary
    return summary.available_balance if summary is not None else status.usdt_balance


def _facts(
    bot: Bot,
    status: ExchangeConnectionStatus,
    orders: tuple[Order, ...],
    earlier: EarlierRunsInventory,
    read_at: datetime,
) -> ExchangeFacts:
    symbol = bot.definition.symbol
    bot_id = bot.bot_id.value
    holdings = status.holdings or ()
    base = symbol.removesuffix(BUDGET_QUOTE_ASSET)
    on_symbol = tuple(order for order in orders if order.symbol == symbol)
    own = tuple(order for order in on_symbol if tag_of(order.client_order_id) == bot_id)
    base_locked = _locked(holdings, base)
    quote_locked = _locked(holdings, BUDGET_QUOTE_ASSET)
    # A part-filled order locks less than it was placed for, and the exchange's
    # locked balance is the truth: the bot's reserve never exceeds it.
    own_sell = sum(
        (order.quantity for order in own if order.side is OrderSide.SELL), _ZERO
    )
    own_buy = sum(
        (
            order.quantity * order.price
            for order in own
            if order.side is OrderSide.BUY and order.price is not None
        ),
        _ZERO,
    )
    facts = ExchangeFacts(
        venue_title=AccountSource.for_venue(bot.definition.venue).venue_title,
        symbol=symbol,
        base_asset=base,
        quote_asset=BUDGET_QUOTE_ASSET,
        read_at=read_at,
        base_free=next((h.free for h in holdings if h.asset == base), _ZERO),
        base_locked=base_locked,
        quote_free=_available_of(status) or _ZERO,
        quote_locked=quote_locked,
        own_sell_base=min(own_sell, base_locked),
        own_buy_quote=min(own_buy, quote_locked),
        own_open_orders=len(own),
        foreign_open_orders=len(on_symbol) - len(own),
        earlier_runs=earlier,
        can_trade=status.can_trade,
    )
    _log_loaded(bot_id, facts)
    return facts


def _locked(holdings: tuple[SpotHolding, ...], asset: str) -> Decimal:
    return next((h.locked for h in holdings if h.asset == asset), _ZERO)


def _log_loaded(bot_id: str, facts: ExchangeFacts) -> None:
    logger.debug(
        "Bot %s: exchange facts read at %s: %s free %s locked %s, %s free %s "
        "locked %s, %d own and %d other orders, earlier runs %s [exchange-facts]",
        bot_id,
        _stamp(facts.read_at),
        facts.base_asset,
        facts.base_free,
        facts.base_locked,
        facts.quote_asset,
        facts.quote_free,
        facts.quote_locked,
        facts.own_open_orders,
        facts.foreign_open_orders,
        facts.earlier_runs.quantity
        if facts.earlier_runs.is_known
        else facts.earlier_runs.unavailable,
    )


def _stamp(moment: datetime) -> str:
    return moment.strftime("%H:%M:%S")
