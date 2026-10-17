"""`EPIC-039L` — the mechanics of one Grid's protective stops: their records and their orders.

@details The part of the stop's life that is not policy. A record is saved with the runtime
**before** the order is sent (decision D5), a move of its state is one row of the lifecycle
table (`protective_stop_fsm_matrix.py`), and an order is sent and cancelled through the bot's
gateway like any other of its orders. What is wanted, and when, is `protection_futures.py`'s.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    OrderOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.protective_stop_request import (
    ProtectiveStopOrder,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop import (
    ProtectiveStop,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.protective_stop_fsm_matrix import (
    ProtectiveStopEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class ProtectiveStopBook:
    """Saves, sends and cancels the protective stops of one bot."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    @property
    def stops(self) -> tuple[ProtectiveStop, ...]:
        return self._context.state.runtime.protective_stops

    def stop_by_id(self, client_order_id: str) -> ProtectiveStop | None:
        return next(
            (s for s in self.stops if s.client_order_id == client_order_id), None
        )

    def intend(self, side: OrderSide, trigger_price: Decimal) -> ProtectiveStop:
        """Save a new stop, its id made here, and have its fills count as an exit's. Nothing
        has been sent: this is the record a crash must find."""
        stop = ProtectiveStop(
            client_order_id=generate_client_order_id(self._context.state.bot_id),
            side=side,
            trigger_price=trigger_price,
        )
        self._save(stop)
        self._context.off_ladder.add_exit(stop.client_order_id)
        logger.info(
            "Bot %s: protective stop %s %s at %s saved before it is sent [protective-stop]",
            self._context.state.bot_id,
            stop.client_order_id,
            stop.side.value,
            stop.trigger_price,
        )
        return stop

    def adopt(
        self, side: OrderSide, trigger_price: Decimal, open_stops: dict[str, Order]
    ) -> bool:
        """A stop of the right side already stands but the record lost it (the app died after
        the order and before the save): it is taken back, never placed twice."""
        tick = self._context.terms.tick_size
        known = {s.client_order_id for s in self.stops}
        for order in open_stops.values():
            if (
                order.side is side
                and order.stop_price is not None
                and abs(order.stop_price - trigger_price) <= tick
                and order.client_order_id not in known
            ):
                stop = ProtectiveStop(
                    order.client_order_id, order.side, order.stop_price
                )
                self._context.off_ladder.add_exit(stop.client_order_id)
                self._save(stop.moved(ProtectiveStopEvent.ACCEPTED) or stop)
                logger.info(
                    "Bot %s: adopted the protective stop %s [protective-stop]",
                    self._context.state.bot_id,
                    stop.client_order_id,
                )
                return True
        return False

    def send(self, stop: ProtectiveStop, mark: Decimal) -> OrderOutcome:
        """Send `stop`, whose record is already saved. Accepted: it is `STANDING`; refused by
        name (the numbers, the market already beyond it): the record is dropped."""
        outcome = self._context.gateway.place_protective_stop(
            ProtectiveStopOrder(
                ClientOrderId(stop.client_order_id),
                stop.side,
                stop.trigger_price,
                mark,
            )
        )
        if outcome.done:
            self.apply(stop, ProtectiveStopEvent.ACCEPTED)
        return outcome

    def apply(self, stop: ProtectiveStop, event: ProtectiveStopEvent) -> None:
        """Move `stop` by `event` and save it; a stop the move ends is dropped."""
        moved = stop.moved(event)
        runtime = self._context.state.runtime
        if moved is None:
            self._context.state.update(runtime.without_stop(stop.client_order_id))
        else:
            self._context.state.update(runtime.with_stop(moved))
        logger.info(
            "Bot %s: protective stop %s %s -> %s [protective-stop]",
            self._context.state.bot_id,
            stop.client_order_id,
            stop.state.value,
            moved.state.value if moved else "dropped",
        )

    def ran(self, stop: ProtectiveStop) -> bool:
        """Whether the exchange ran `stop`: its status by client id says the trigger traded.
        `EXPIRED`/`CANCELED` is the exchange ending it without a fill (check T2); a status that
        cannot be read counts as ran, the side that ends flat and stops the bot."""
        status = self._context.gateway.account_reads.order_status(stop.client_order_id)
        if status in (OrderStatus.EXPIRED, OrderStatus.CANCELED):
            logger.info(
                "Bot %s: the exchange ended the protective stop %s as %s without a fill "
                "[protective-stop]",
                self._context.state.bot_id,
                stop.client_order_id,
                status.value,
            )
            return False
        if status not in (OrderStatus.TRIGGERED, OrderStatus.FILLED):
            logger.warning(
                "Bot %s: how the protective stop %s ended could not be read (%s); taking it "
                "as triggered [protective-stop]",
                self._context.state.bot_id,
                stop.client_order_id,
                status,
            )
        return True

    def cancel(self, stop: ProtectiveStop) -> OrderOutcome:
        """Cancel `stop`'s order. Whether the exchange still holds it is read by the caller."""
        return self._context.gateway.cancel(stop.client_order_id)

    def _save(self, stop: ProtectiveStop) -> None:
        runtime = self._context.state.runtime
        self._context.state.update(runtime.with_stop(stop))
