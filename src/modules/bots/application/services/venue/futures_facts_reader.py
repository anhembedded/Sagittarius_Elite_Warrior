"""`EPIC-039E` — reads a Futures venue's facts about one bot's symbol and account.

@details The Futures adapter of `IVenueFacts`: the account's available margin and position
mode (the connection check), the symbol's leverage and margin type (`symbolConfig`, since
`positionRisk` v3 has neither, `BUG-114`), its leverage brackets, the orders resting on
the symbol (the bot's own apart from the rest) and the signed position. Never raises: a read
that failed is `ExchangeUnavailable` with the reason in words, so a rule can never mistake a
failed read for a flat, empty account. A Hedge Mode account is refused with the Connect
step's own words (`connect_failure_words`).

Every read is read-only, through the venue's trading ports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.connect_failure_words import (
    failure_state,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesFacts,
    FuturesLoaded,
    FuturesSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_facts import (
    IVenueFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_rejected_error import (
    AccountControlRejectedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_unavailable_error import (
    AccountControlUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

logger = logging.getLogger("App.Bots.Readiness")

_ZERO = Decimal(0)
_QUOTE_ASSET = "USDT"


@dataclass(frozen=True, slots=True)
class _AccountReading:
    """What the connection check says about the account, once it is known to be whole."""

    margin: Decimal
    mode: PositionMode
    can_trade: bool | None


class FuturesFactsReader(IVenueFacts):
    """@brief What a Futures venue says about `bot`'s symbol and account, now."""

    def __init__(self, ports: IVenueTradingPorts, clock: IBotClock) -> None:
        self._ports = ports
        self._clock = clock

    def read(self, bot: Bot) -> FuturesSnapshot:
        definition = bot.definition
        try:
            ports = self._ports.get(definition.venue)
        except VenueNotEnabledError:
            return self._unavailable(
                bot, f"{definition.venue.display_name} is not enabled"
            )
        status = ports.account_snapshot.check_connection()
        problem = _connection_problem(bot, status)
        if problem is not None:
            return self._unavailable(bot, problem)
        margin = _available_margin_of(status)
        mode = status.position_mode
        if margin is None or mode is None:
            return self._unavailable(bot, "the account's margin and mode were not read")
        try:
            facts = self._facts(
                bot, ports, _AccountReading(margin, mode, status.can_trade)
            )
        except (AccountControlRejectedError, AccountControlUnavailableError) as error:
            return self._unavailable(
                bot, f"the symbol's settings were not read ({error})"
            )
        except Exception as exc:  # noqa: BLE001 - converted at the seam: any failed read (network, rate limit, key) is an unavailable snapshot, never a thrown error and never a flat account
            logger.debug("Futures facts of %s not read: %s", definition.symbol, exc)
            return self._unavailable(bot, f"the venue's facts were not read ({exc})")
        logger.debug(
            "Bot %s: futures facts read: margin %s, position %s, leverage %d, "
            "%d own and %d other orders [exchange-facts]",
            bot.bot_id.value,
            facts.available_margin,
            facts.position,
            facts.symbol_setting.leverage,
            facts.own_open_orders,
            facts.foreign_open_orders,
        )
        return FuturesLoaded(facts)

    def _facts(
        self, bot: Bot, ports: VenueTradingPorts, account: _AccountReading
    ) -> FuturesFacts:
        definition = bot.definition
        symbol = definition.symbol
        setting = ports.order_entry_terms.futures_setting_for(symbol)
        brackets = ports.order_entry_terms.leverage_brackets_for(symbol)
        if isinstance(setting, NotApplicable) or isinstance(brackets, NotApplicable):
            raise AccountControlUnavailableError(
                f"{definition.venue.display_name} has no leverage to read"
            )
        on_symbol = tuple(
            o for o in ports.account_activity.open_orders() if o.symbol == symbol
        )
        own = sum(1 for o in on_symbol if tag_of(o.client_order_id) == bot.bot_id.value)
        position = sum(
            (
                p.position_amt
                for p in ports.account_snapshot.open_positions()
                if p.symbol == symbol
            ),
            _ZERO,
        )
        return FuturesFacts(
            venue_title=AccountSource.for_venue(definition.venue).venue_title,
            symbol=symbol,
            quote_asset=_QUOTE_ASSET,
            read_at=self._clock.now(),
            available_margin=account.margin,
            position=position,
            position_mode=account.mode,
            symbol_setting=setting,
            brackets=brackets,
            own_open_orders=own,
            foreign_open_orders=len(on_symbol) - own,
            can_trade=account.can_trade,
        )

    def _unavailable(self, bot: Bot, reason: str) -> ExchangeUnavailable:
        logger.info(
            "Bot %s: the venue's futures facts are unavailable: %s [exchange-facts]",
            bot.bot_id.value,
            reason,
        )
        return ExchangeUnavailable(reason)


def _connection_problem(bot: Bot, status: ExchangeConnectionStatus) -> str | None:
    if status.failure is None and status.reachable:
        return None
    source = AccountSource.for_venue(bot.definition.venue)
    kind = status.failure or ConnectionFailureKind.NETWORK
    return failure_state(ConnectFailure(source, kind, "the account"))


def _available_margin_of(status: ExchangeConnectionStatus) -> Decimal | None:
    summary = status.summary
    return summary.available_balance if summary is not None else status.usdt_balance
