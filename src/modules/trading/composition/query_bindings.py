"""trading's read side: the queries the Trading screen, Dev Board and (from
`EPIC-028E`) the desks' history tabs dispatch.

`EPIC-025E` PR 4.4f-4 — moved out of `binance_bot_module.py`, same shape
`command_bindings.py` in this package already uses.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
    PreviewOrderQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_account_summary import (
    GetAccountSummaryQuery,
    GetAccountSummaryQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_average_entry_price import (
    GetAverageEntryPriceQuery,
    GetAverageEntryPriceQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_best_bid_ask import (
    GetBestBidAskQuery,
    GetBestBidAskQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_commission_rate import (
    GetCommissionRateQuery,
    GetCommissionRateQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_exchange_connection_status import (
    GetExchangeConnectionStatusQuery,
    GetExchangeConnectionStatusQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_futures_symbol_setting import (
    GetFuturesSymbolSettingQuery,
    GetFuturesSymbolSettingQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_holdings import (
    GetHoldingsQuery,
    GetHoldingsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_leverage_brackets import (
    GetLeverageBracketsQuery,
    GetLeverageBracketsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_mark_price import (
    GetMarkPriceQuery,
    GetMarkPriceQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_orders import (
    GetOpenOrdersQuery,
    GetOpenOrdersQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
    GetOpenPositionsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_history import (
    GetOrderHistoryQuery,
    GetOrderHistoryQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_notional_limit import (
    GetOrderNotionalLimitQuery,
    GetOrderNotionalLimitQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_symbol_order_rules import (
    GetSymbolOrderRulesQuery,
    GetSymbolOrderRulesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_trade_history import (
    GetTradeHistoryQuery,
    GetTradeHistoryQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.list_venue_keys import (
    ListVenueKeysQuery,
    ListVenueKeysQueryHandler,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_queries(container: IContainer) -> None:
    """Route each trading query type to the handler that answers it."""
    container.bind(GetOpenPositionsQuery, GetOpenPositionsQueryHandler)
    container.bind(GetHoldingsQuery, GetHoldingsQueryHandler)
    container.bind(GetAccountSummaryQuery, GetAccountSummaryQueryHandler)
    container.bind(
        GetExchangeConnectionStatusQuery, GetExchangeConnectionStatusQueryHandler
    )
    container.bind(PreviewOrderQuery, PreviewOrderQueryHandler)
    container.bind(GetOpenOrdersQuery, GetOpenOrdersQueryHandler)
    container.bind(GetOrderHistoryQuery, GetOrderHistoryQueryHandler)
    container.bind(GetTradeHistoryQuery, GetTradeHistoryQueryHandler)
    container.bind(GetAverageEntryPriceQuery, GetAverageEntryPriceQueryHandler)
    container.bind(GetCommissionRateQuery, GetCommissionRateQueryHandler)
    container.bind(GetSymbolOrderRulesQuery, GetSymbolOrderRulesQueryHandler)
    # EPIC-028O: the reads the desks size orders and show figures with.
    container.bind(GetFuturesSymbolSettingQuery, GetFuturesSymbolSettingQueryHandler)
    container.bind(GetLeverageBracketsQuery, GetLeverageBracketsQueryHandler)
    container.bind(GetMarkPriceQuery, GetMarkPriceQueryHandler)
    container.bind(GetBestBidAskQuery, GetBestBidAskQueryHandler)
    container.bind(GetOrderNotionalLimitQuery, GetOrderNotionalLimitQueryHandler)
    # BUG-176: the Options page lists each venue's key as a fingerprint.
    container.bind(ListVenueKeysQuery, ListVenueKeysQueryHandler)
