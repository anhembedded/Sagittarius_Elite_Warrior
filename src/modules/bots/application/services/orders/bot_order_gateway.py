"""`EPIC-029E` — how one bot asks trading for its orders (ADR D1, D5, D9).

Trading stays the only module that sends orders; this is the bot's side of that
conversation. Every order carries the bot's owner id (the lease) and its tag
(D5: `SEW-{tag}-…`, so trading counts it against the bot's budget and the bot
recognises it in account-wide reads). Every order waits its turn on the pacer
(D6 check 4).

**Every answer is classified (D9).** A refusal is a value, never an exception:

  · `SWITCH_OFF` — `TRADING_SWITCH_OFF` or `CONNECTION_NOT_READY`. The order
    session is closed (Emergency Stop) or not yet connected; the bot halts (or waits, when STOPPING). Never a
    fault: an Emergency Stop racing a submit must lead to HALTED, not ERROR.
  · `KEY_REJECTED` — the exchange rejected the API key (`EPIC-035F`), on the
    connection check or on the order itself. Not a switch-off: nothing a wait
    can mend, and the orders already on the exchange cannot be cancelled.
  · `REFUSED` — any other gate or limit, or the exchange's minimum notional;
    the bot halts naming it.
  · `SYMBOL_NOT_TRADING` / `SYMBOL_NOT_LISTED` — the exchange refused the order
    because of the symbol's status, or no longer knows the symbol (`EPIC-035E`).
    Not faults: the bot pauses or halts naming it.
  · `ORDER_INVALID` — the order's own numbers were refused, by trading before it
    sent (the percent-price band, the minimum notional) or by the exchange
    (`LOT_SIZE`, `PRICE_FILTER`, `MIN_NOTIONAL`, `-2010`) (`EPIC-035T`). A fault
    of one order, not of the bot: a RUNNING ladder leaves that rung EMPTY.
  · `RATE_LIMITED` — the exchange (or the venue's gate, closed by another call)
    asked for a pause (`EPIC-035D`). Nothing was sent or placed, so it is no fault:
    the bot halts for the stated pause, or its stop waits it out.
  · `FAULT` — the request raised (the venue rejected what it received, or the
    request never arrived). The one place an exception from trading is caught,
    because here it becomes a named fault for the lifecycle (`code/errors.md`:
    converted at the seam, never swallowed; the traceback is logged).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_account_reads import (
    BotAccountReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_identity import (
    BotIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_history import (
    BotOrderHistory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.order_outcome import (
    SWITCH_OFF_GATES,
    OrderOutcome,
    OrderOutcomeKind,
    classify_cancel,
    classify_submit,
    fault_text,
    named_rejection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.protective_stop_request import (
    ProtectiveStopOrder,
    protective_stop_request,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.rate_limit_pause import (
    whole_seconds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderNotPlacedError,
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)

__all__ = [
    "SWITCH_OFF_GATES",
    "BotIdentity",
    "BotOrderGateway",
    "OrderOutcome",
    "OrderOutcomeKind",
]

logger = logging.getLogger("App.Bots.GridExecutor")


class BotOrderGateway:
    """Places, cancels and lists one bot's orders on its venue."""

    def __init__(
        self, ports: VenueTradingPorts, identity: BotIdentity, pacer: IOrderPacer
    ) -> None:
        self._ports = ports
        self._identity = identity
        self._pacer = pacer
        self._history = BotOrderHistory(ports.account_activity, identity.symbol)
        self._reads = BotAccountReads(ports, identity)
        self._submissions = 0
        self._rate_limit: timedelta | None = None

    @property
    def submissions(self) -> int:
        """Orders this gateway has sent to trading, whatever came back: a
        request that raised may still have reached the exchange, so it counts.
        A task that moved this number may have left orders resting
        (`GridTaskGuard`)."""
        return self._submissions

    def note_rate_limit(self, retry_after: timedelta) -> None:
        """Remember the pause the exchange last asked of this bot."""
        self._rate_limit = retry_after

    def take_rate_limit(self) -> timedelta | None:
        """The pause the exchange last asked of this bot since it was last
        taken, or `None`: a halt for a rate limit schedules its resume by it."""
        taken, self._rate_limit = self._rate_limit, None
        return taken

    def place_limit(
        self,
        side: OrderSide,
        price: Decimal,
        quantity: Decimal,
        *,
        reduce_only: bool = False,
    ) -> OrderOutcome:
        """A LIMIT GTC order at `price`; `reduce_only` on a position venue's exits
        (`EPIC-039H`, `IOrderFlags`)."""
        return self._submit(
            self._request(
                side,
                OrderType.LIMIT,
                quantity,
                price,
                TimeInForce.GTC,
                reduce_only=reduce_only,
            )
        )

    def market_buy(self, quote: Decimal, reference_price: Decimal) -> OrderOutcome:
        """A market BUY spending `quote` (Spot `quoteOrderQty`)."""
        request = OrderRequest(
            symbol=self._identity.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=quote / reference_price,
            reference_price=reference_price,
            owner_id=self._identity.owner_id,
            quote_quantity=quote,
            client_order_tag=self._identity.tag,
        )
        return self._submit(request)

    def market_base(
        self, side: OrderSide, quantity: Decimal, reference_price: Decimal
    ) -> OrderOutcome:
        """A market order of `quantity` base on `side`: what a position venue's opening sends,
        where there is no quote-sized order (`EPIC-039H`; a SELL opens a short, `EPIC-039I`)."""
        return self._submit(
            self._request(side, OrderType.MARKET, quantity, reference_price)
        )

    def market_sell(self, quantity: Decimal, reference_price: Decimal) -> OrderOutcome:
        """A market SELL of `quantity` base."""
        return self._submit(
            self._request(OrderSide.SELL, OrderType.MARKET, quantity, reference_price)
        )

    def market_reduce_only(
        self, side: OrderSide, quantity: Decimal, reference_price: Decimal
    ) -> OrderOutcome:
        """A market order of `quantity` base on `side` that may only shrink the position:
        the exchange refuses it when it would grow or flip one (`EPIC-039H`), which is what
        makes a close safe to send twice."""
        return self._submit(
            self._request(
                side, OrderType.MARKET, quantity, reference_price, reduce_only=True
            )
        )

    def cancel(self, client_order_id: str) -> OrderOutcome:
        try:
            result = self._ports.order_submission.cancel(
                self._identity.symbol, client_order_id
            )
        except ExchangeRateLimitedError as limited:
            return self._rate_limited(limited, client_order_id)
        except Exception as exc:  # converted to a named outcome at this seam
            named = named_rejection(exc)
            if named is not None and named.kind is OrderOutcomeKind.KEY_REJECTED:
                logger.warning(
                    "Bot %s: cancel %s was refused by name: %s [named-refusal]",
                    self._identity.tag,
                    client_order_id,
                    named.kind.value,
                )
                return OrderOutcome(named.kind, client_order_id, named.detail)
            logger.exception(
                "Bot %s: cancel %s raised", self._identity.tag, client_order_id
            )
            return OrderOutcome(
                OrderOutcomeKind.FAULT, client_order_id, fault_text(exc)
            )
        return classify_cancel(result, client_order_id)

    def market_price(self) -> Decimal:
        """The middle of the symbol's best bid and ask, for a market order's
        reference when no tick has been heard yet."""
        book = self._ports.order_entry_terms.best_bid_ask_for(self._identity.symbol)
        return (book.bid_price + book.ask_price) / 2

    def order_record(self, client_order_id: str, since: datetime) -> OrderRecord | None:
        """The venue's history of one of the bot's orders, or `None` when
        the history since `since` does not hold it.
        @raise AccountHistoryUnavailableError The venue did not answer."""
        return self._history.order_record(client_order_id, since)

    def order_records(
        self, client_order_ids: frozenset[str], since: datetime
    ) -> dict[str, OrderRecord]:
        """The venue's history of each of the named orders that `since` holds,
        read in one pass (`BotOrderHistory`).
        @raise AccountHistoryUnavailableError The venue did not answer."""
        return self._history.order_records(client_order_ids, since)

    def order_trades(
        self, exchange_order_id: int, since: datetime
    ) -> tuple[TradeRecord, ...]:
        """Every fill of one of the bot's orders since `since`, with its fee.
        @raise AccountHistoryUnavailableError The venue did not answer."""
        return self._history.order_trades(exchange_order_id, since)

    def holding(self, asset: str) -> Decimal | None:
        """The account's whole holding of `asset`, or `None` (`BotAccountReads`)."""
        return self._reads.holding(asset)

    def position(self) -> Decimal | None:
        """The account's signed position on the bot's symbol, `None` when the read failed
        (`BotAccountReads`; `EPIC-039H`: a close is confirmed from this and nothing else)."""
        return self._reads.position()

    def connection_failure(self) -> ConnectionFailureKind | None:
        """Why the venue's account cannot be read now, or `None` (`BotAccountReads`)."""
        return self._reads.connection_failure()

    def tagged_open_orders(self) -> tuple[Order, ...]:
        """The bot's **ladder** orders that are open: those carrying its tag, without its
        protective stops (`EPIC-039L`, decision D4: one seam, so no ladder read sees a stop)."""
        return self._reads.ladder_orders()

    @property
    def account_reads(self) -> BotAccountReads:
        """The bot's reads of its account beyond the ladder: its protective stops and how one
        order ended (`EPIC-039L`). A property, so the gateway's own surface stays small."""
        return self._reads

    def place_protective_stop(self, stop: ProtectiveStopOrder) -> OrderOutcome:
        """A stop that closes the whole position when the mark price reaches `stop`'s trigger
        (`EPIC-039L`): sent as a protective order, so the trading limits that pace new trades
        do not refuse it."""
        return self._submit(protective_stop_request(stop, self._identity))

    def _request(
        self,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal,
        time_in_force: TimeInForce | None = None,
        *,
        reduce_only: bool = False,
    ) -> OrderRequest:
        return OrderRequest(
            symbol=self._identity.symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            reference_price=price,
            reduce_only=reduce_only,
            owner_id=self._identity.owner_id,
            time_in_force=time_in_force,
            client_order_tag=self._identity.tag,
        )

    def _submit(self, request: OrderRequest) -> OrderOutcome:
        self._pacer.wait_turn()
        self._submissions += 1
        try:
            result = self._ports.order_submission.submit(request, live=True)
        except ExchangeRateLimitedError as limited:
            # Nothing reached the exchange's order book: it answered the limit
            # before reading the order, or the venue's gate stopped it.
            return self._rate_limited(limited, "")
        except OrderOutcomeUnknownError as unknown:
            # `BUG-170` — the order may be live. The id is carried so the stop
            # sequence marks it off the ladder and a later fill is booked as
            # what it is; the bot itself stops in ERROR, never retries blind.
            logger.error(
                "Bot %s: order %s outcome unknown, it may be live: %s",
                self._identity.tag,
                unknown.client_order_id,
                unknown.reason,
            )
            return OrderOutcome(
                OrderOutcomeKind.FAULT, unknown.client_order_id, str(unknown)
            )
        except OrderNotPlacedError as refused:
            logger.warning(
                "Bot %s: order %s was not placed: %s",
                self._identity.tag,
                refused.client_order_id,
                refused.reason,
            )
            return OrderOutcome(OrderOutcomeKind.FAULT, detail=str(refused))
        except Exception as exc:  # converted to a named outcome at this seam
            named = named_rejection(exc)
            if named is not None:
                logger.warning(
                    "Bot %s: %s %s was refused by name: %s [named-refusal]",
                    self._identity.tag,
                    request.order_type.value,
                    request.side.value,
                    named.kind.value,
                )
                return named
            logger.exception(
                "Bot %s: %s %s %s raised",
                self._identity.tag,
                request.order_type.value,
                request.side.value,
                request.quantity,
            )
            return OrderOutcome(OrderOutcomeKind.FAULT, detail=fault_text(exc))
        return classify_submit(result)

    def _rate_limited(
        self, limited: ExchangeRateLimitedError, client_order_id: str
    ) -> OrderOutcome:
        self.note_rate_limit(limited.retry_after)
        logger.warning(
            "Bot %s: rate limited, the exchange asked for %d s%s [bot-rate-limited]",
            self._identity.tag,
            whole_seconds(limited.retry_after),
            " (a ban)" if limited.banned else "",
        )
        return OrderOutcome(
            OrderOutcomeKind.RATE_LIMITED,
            client_order_id,
            f"rate limited: the exchange asked for a pause of "
            f"{whole_seconds(limited.retry_after)} s",
            limited.retry_after,
        )
