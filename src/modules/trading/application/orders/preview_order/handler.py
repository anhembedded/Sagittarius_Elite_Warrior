import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.stop_price_check import (
    StopPriceCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.stop_trigger_side import (
    check_stop_trigger_side,
)

#: The order types that rest on the book and so carry a price and a time in
#: force (`EPIC-028O` adds `STOP_LIMIT`).
_RESTING_TYPES = frozenset({OrderType.LIMIT, OrderType.STOP_LIMIT})

logger = logging.getLogger("App.QueryHandler")


class PreviewOrderQueryHandler(IQueryHandler[PreviewOrderQuery, OrderPreview]):
    """
    @brief Handler for `PreviewOrderQuery` (`EPIC-021E`).

    @details The one point in this task where a network call can happen:
    `IMarketMetadataProvider.get_or_fetch()` fetches Binance's
    `exchangeInfo` the first time a symbol isn't cached yet. Unlike
    `ITradingAccountReader` (`EPIC-021D`), that port makes no "never
    raises" promise — so this handler does not swallow a network failure
    either; the CLI entry point that calls it is where that gets caught
    and shown as a named, friendly failure, the same layer boundary
    `exchange-status` already uses.
    """

    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts
        self._rounding_policy = OrderQuantityRoundingPolicy()

    def execute(self, query: PreviewOrderQuery) -> OrderPreview:
        """@details `EPIC-028B` — rounds against `query.venue`'s own rules:
        a Futures and a Spot `BTCUSDT` are different instruments with
        different lot sizes."""
        logger.debug(
            "Handling PreviewOrderQuery for %s on %s", query.symbol, query.venue.value
        )
        metadata_provider = self._contexts.get(query.venue).metadata_provider
        metadata = metadata_provider.get_or_fetch(query.symbol)
        if metadata is None:
            raise ValueError(f"Unknown symbol on {query.venue.value}: {query.symbol}")

        step_size = metadata.step_size_for(query.order_type)
        rounded_price = self._rounding_policy.round_price_to_tick(
            query.reference_price, metadata.tick_size, query.side
        )
        # `EPIC-028O` — a quote-sized market buy spends exactly its quote
        # amount; its base quantity is only the estimate at the reference
        # price, and the notional the exchange checks is the quote amount.
        raw_quantity = (
            query.quote_quantity / rounded_price
            if query.quote_quantity is not None
            else query.quantity
        )
        rounded_quantity = self._rounding_policy.round_quantity_down(
            raw_quantity, step_size
        )
        notional = (
            query.quote_quantity
            if query.quote_quantity is not None
            else rounded_quantity * rounded_price
        )
        notional_check = self._rounding_policy.is_notional_sufficient(
            notional, Decimal(1), metadata.min_notional
        )

        resting = query.order_type in _RESTING_TYPES
        stop_price, stop_check = self._stop(query, metadata.tick_size)
        # `BUG-116` — a resting order needs a time in force or the mappers
        # refuse it; GTC unless the caller chose (`EPIC-028O`).
        order = Order(
            client_order_id=generate_client_order_id(),
            symbol=query.symbol,
            side=query.side,
            order_type=query.order_type,
            quantity=rounded_quantity,
            price=rounded_price if resting else None,
            stop_price=stop_price,
            time_in_force=(query.time_in_force or TimeInForce.GTC) if resting else None,
            reduce_only=query.reduce_only,
            quote_quantity=query.quote_quantity,
        )

        return OrderPreview(
            order=order,
            raw_quantity=raw_quantity,
            estimated_notional=notional,
            min_notional=metadata.min_notional,
            step_size=step_size,
            notional_check=notional_check,
            stop_check=stop_check,
        )

    def _stop(
        self, query: PreviewOrderQuery, tick_size: Decimal
    ) -> tuple[Decimal | None, StopPriceCheck | None]:
        """`EPIC-028O` — the stop price rounded to the tick *away* from the
        market (up for a buy stop, down for a sell stop: the opposite of a
        limit price, so rounding never moves a stop onto the crossed side),
        and whether it then waits for the market."""
        if query.stop_price is None or query.last_price is None:
            return None, None
        away = OrderSide.SELL if query.side is OrderSide.BUY else OrderSide.BUY
        stop = self._rounding_policy.round_price_to_tick(
            query.stop_price, tick_size, away
        )
        return stop, check_stop_trigger_side(query.side, stop, query.last_price)
