"""`EPIC-027C` — the exchange metadata a run's filters come from."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exchange_filters import (
    ExchangeFilters,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    SymbolMarketMetadata,
)

logger = logging.getLogger("App.BackTestPresenter")


def exchange_filters_from_metadata(
    metadata: SymbolMarketMetadata | None,
) -> ExchangeFilters | None:
    """@brief The filters a run applies for one (market, symbol), copied from
    its cached exchange metadata.
    @return `None` when there is no metadata, or when it holds a value no
    exchange rule can take (a zero step size): the run then applies no filter
    and its result says so, rather than trading on an invented rule."""
    if metadata is None:
        return None
    try:
        return ExchangeFilters(
            step_size=metadata.lot_size_filter.step_size,
            min_quantity=metadata.lot_size_filter.min_qty,
            min_notional=metadata.notional_filter.min_notional,
            tick_size=metadata.price_filter.tick_size,
        )
    except ValueError as exc:
        logger.warning(
            "[exchange-filter] %s metadata is unusable (%s); the run applies no "
            "exchange filter.",
            metadata.symbol,
            exc,
        )
        return None
