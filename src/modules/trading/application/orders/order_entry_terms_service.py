"""`EPIC-028H` — `IOrderEntryTerms`, implemented over two venue-addressed
queries: the symbol's order filters and the account's commission rate.

Same shape as `AccountSnapshotService`: a façade over the dispatcher, one
instance per venue, adding a name and a type and no rule.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_commission_rate.query import (
    GetCommissionRateQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_symbol_order_rules.query import (
    GetSymbolOrderRulesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_entry_terms import (
    IOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_entry_terms import (
    OrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class OrderEntryTermsService(IOrderEntryTerms):
    """The order-entry terms of one venue (`EPIC-028H`)."""

    def __init__(self, dispatcher: ICommandDispatcher, venue: TradingVenue) -> None:
        self._dispatcher = dispatcher
        self._venue = venue

    def terms_for(self, symbol: str) -> OrderEntryTerms:
        rules = self._dispatcher.dispatch(
            GetSymbolOrderRulesQuery,
            GetSymbolOrderRulesQuery(venue=self._venue, symbol=symbol),
        )
        commission = self._dispatcher.dispatch(
            GetCommissionRateQuery,
            GetCommissionRateQuery(venue=self._venue, symbol=symbol),
        )
        if not isinstance(rules, SymbolOrderMetadata) or not isinstance(
            commission, CommissionRate
        ):
            raise TypeError(
                "the order-entry terms were not answered with "
                "SymbolOrderMetadata and CommissionRate but with "
                f"{type(rules).__name__} and {type(commission).__name__} "
                "— a handler is not bound"
            )
        return OrderEntryTerms(rules=rules, commission=commission)
