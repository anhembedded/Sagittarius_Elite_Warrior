"""`EPIC-029E` — how one bot asks trading for its orders (ADR D1, D5, D9).

Trading stays the only module that sends orders; this is the bot's side of that
conversation. Every order carries the bot's owner id (the lease) and its tag
(D5: `SEW-{tag}-…`, so trading counts it against the bot's budget and the bot
recognises it in account-wide reads). Every order waits its turn on the pacer
(D6 check 4).

**Every answer is classified (D9).** A refusal is a value, never an exception:

  · `SWITCH_OFF` — `TRADING_SWITCH_OFF` or `CONNECTION_NOT_READY`. Trading is
    off or not yet connected; the bot halts (or waits, when STOPPING). Never a
    fault: an Emergency Stop racing a submit must lead to HALTED, not ERROR.
  · `REFUSED` — any other gate or limit, or the exchange's minimum notional;
    the bot halts naming it.
  · `FAULT` — the request raised (the venue rejected what it received, or the
    request never arrived). The one place an exception from trading is caught,
    because here it becomes a named fault for the lifecycle (`code/errors.md`:
    converted at the seam, never swallowed; the traceback is logged).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.cancel_order_result import (
    CancelOrderResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderResult,
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    OrderRequest,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_trading_ports import (
    VenueTradingPorts,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: The refusals that mean "trading is off", not "this order is wrong" (D9).
SWITCH_OFF_GATES: frozenset[ExecuteOrderSafetyGate] = frozenset(
    {
        ExecuteOrderSafetyGate.TRADING_SWITCH_OFF,
        ExecuteOrderSafetyGate.CONNECTION_NOT_READY,
    }
)


class OrderOutcomeKind(str, Enum):
    DONE = "done"
    SWITCH_OFF = "switch_off"
    REFUSED = "refused"
    FAULT = "fault"


@dataclass(frozen=True, slots=True)
class OrderOutcome:
    """What trading answered: done (with the order's id) or why not."""

    kind: OrderOutcomeKind
    client_order_id: str = ""
    detail: str = ""

    @property
    def done(self) -> bool:
        return self.kind is OrderOutcomeKind.DONE


@dataclass(frozen=True, slots=True)
class BotIdentity:
    """Who the bot is to trading: its owner id, its tag, the symbol it trades."""

    owner_id: str
    tag: str
    symbol: str


class BotOrderGateway:
    """Places, cancels and lists one bot's orders on its venue."""

    def __init__(
        self, ports: VenueTradingPorts, identity: BotIdentity, pacer: IOrderPacer
    ) -> None:
        self._ports = ports
        self._identity = identity
        self._pacer = pacer

    def place_limit(
        self, side: OrderSide, price: Decimal, quantity: Decimal
    ) -> OrderOutcome:
        """A LIMIT GTC order at `price`."""
        return self._submit(
            self._request(side, OrderType.LIMIT, quantity, price, TimeInForce.GTC)
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

    def market_sell(self, quantity: Decimal, reference_price: Decimal) -> OrderOutcome:
        """A market SELL of `quantity` base."""
        return self._submit(
            self._request(OrderSide.SELL, OrderType.MARKET, quantity, reference_price)
        )

    def cancel(self, client_order_id: str) -> OrderOutcome:
        try:
            result = self._ports.order_submission.cancel(
                self._identity.symbol, client_order_id
            )
        except Exception as exc:  # converted to a named fault at this seam
            logger.exception(
                "Bot %s: cancel %s raised", self._identity.tag, client_order_id
            )
            return OrderOutcome(OrderOutcomeKind.FAULT, client_order_id, str(exc))
        return _classify_cancel(result, client_order_id)

    def market_price(self) -> Decimal:
        """The middle of the symbol's best bid and ask, for a market order's
        reference when no tick has been heard yet."""
        book = self._ports.order_entry_terms.best_bid_ask_for(self._identity.symbol)
        return (book.bid_price + book.ask_price) / 2

    def tagged_open_orders(self) -> tuple[Order, ...]:
        """The account's open orders on the bot's symbol that carry its tag."""
        return tuple(
            order
            for order in self._ports.account_activity.open_orders()
            if order.symbol == self._identity.symbol
            and tag_of(order.client_order_id) == self._identity.tag
        )

    def _request(
        self,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal,
        time_in_force: TimeInForce | None = None,
    ) -> OrderRequest:
        return OrderRequest(
            symbol=self._identity.symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            reference_price=price,
            owner_id=self._identity.owner_id,
            time_in_force=time_in_force,
            client_order_tag=self._identity.tag,
        )

    def _submit(self, request: OrderRequest) -> OrderOutcome:
        self._pacer.wait_turn()
        try:
            result = self._ports.order_submission.submit(request, live=True)
        except Exception as exc:  # converted to a named fault at this seam
            logger.exception(
                "Bot %s: %s %s %s raised",
                self._identity.tag,
                request.order_type.value,
                request.side.value,
                request.quantity,
            )
            return OrderOutcome(OrderOutcomeKind.FAULT, detail=str(exc))
        return _classify_submit(result)


def _classify_submit(result: ExecuteOrderResult) -> OrderOutcome:
    if result.blocked_by is not None:
        return _refusal(result.blocked_by, "")
    if result.submitted_order is None:
        return OrderOutcome(OrderOutcomeKind.FAULT, detail="trading returned no order")
    return OrderOutcome(OrderOutcomeKind.DONE, result.submitted_order.client_order_id)


def _classify_cancel(result: CancelOrderResult, client_order_id: str) -> OrderOutcome:
    if result.blocked_by is not None:
        return _refusal(result.blocked_by, client_order_id)
    return OrderOutcome(OrderOutcomeKind.DONE, client_order_id)


def _refusal(blocked_by: Enum, client_order_id: str) -> OrderOutcome:
    kind = (
        OrderOutcomeKind.SWITCH_OFF
        if blocked_by in SWITCH_OFF_GATES
        else OrderOutcomeKind.REFUSED
    )
    return OrderOutcome(kind, client_order_id, str(blocked_by.value))
