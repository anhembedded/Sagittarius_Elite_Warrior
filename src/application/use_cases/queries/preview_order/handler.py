import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.order_preview import (
    OrderPreview,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.preview_order.query import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.domain.policies.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType

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

    def __init__(self, metadata_provider: IMarketMetadataProvider) -> None:
        self._metadata_provider = metadata_provider
        self._rounding_policy = OrderQuantityRoundingPolicy()

    def execute(self, query: PreviewOrderQuery) -> OrderPreview:
        logger.debug("Handling PreviewOrderQuery for %s", query.symbol)
        metadata = self._metadata_provider.get_or_fetch(query.symbol)
        if metadata is None:
            raise ValueError(f"Unknown futures symbol: {query.symbol}")

        rounded_quantity = self._rounding_policy.round_quantity_down(
            query.quantity, metadata.step_size
        )
        rounded_price = self._rounding_policy.round_price_to_tick(
            query.reference_price, metadata.tick_size, query.side
        )
        notional_check = self._rounding_policy.is_notional_sufficient(
            rounded_quantity, rounded_price, metadata.min_notional
        )

        order = Order(
            client_order_id=generate_client_order_id(),
            symbol=query.symbol,
            side=query.side,
            order_type=query.order_type,
            quantity=rounded_quantity,
            price=rounded_price if query.order_type is OrderType.LIMIT else None,
            reduce_only=query.reduce_only,
        )

        return OrderPreview(
            order=order,
            raw_quantity=query.quantity,
            estimated_notional=rounded_quantity * rounded_price,
            min_notional=metadata.min_notional,
            step_size=metadata.step_size,
            notional_check=notional_check,
        )
