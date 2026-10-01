"""`EPIC-028H` — `IOrderEntryTerms`, implemented over venue-addressed
queries.

Same shape as `AccountSnapshotService`: a façade over the dispatcher, one
instance per venue, adding a name and a type and no rule. `EPIC-028O` adds
one query per new read; each answer's type is checked, so an unbound handler
is named instead of handing `None` to a panel.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_best_bid_ask.query import (
    GetBestBidAskQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_commission_rate.query import (
    GetCommissionRateQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_futures_symbol_setting.query import (
    GetFuturesSymbolSettingQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_leverage_brackets.query import (
    GetLeverageBracketsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_mark_price.query import (
    GetMarkPriceQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_notional_limit.query import (
    GetOrderNotionalLimitQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_symbol_order_rules.query import (
    GetSymbolOrderRulesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_entry_terms import (
    IOrderEntryTerms,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import (
    MarkPrice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
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
        rules = self._ask(
            GetSymbolOrderRulesQuery(venue=self._venue, symbol=symbol),
            SymbolOrderMetadata,
        )
        commission = self._ask(
            GetCommissionRateQuery(venue=self._venue, symbol=symbol), CommissionRate
        )
        return OrderEntryTerms(rules=rules, commission=commission)

    def futures_setting_for(self, symbol: str) -> FuturesSymbolSetting | NotApplicable:
        return self._ask_unless_not_applicable(
            GetFuturesSymbolSettingQuery(venue=self._venue, symbol=symbol),
            FuturesSymbolSetting,
        )

    def leverage_brackets_for(self, symbol: str) -> LeverageBrackets | NotApplicable:
        return self._ask_unless_not_applicable(
            GetLeverageBracketsQuery(venue=self._venue, symbol=symbol),
            LeverageBrackets,
        )

    def mark_price_for(self, symbol: str) -> MarkPrice | NotApplicable:
        return self._ask_unless_not_applicable(
            GetMarkPriceQuery(venue=self._venue, symbol=symbol), MarkPrice
        )

    def best_bid_ask_for(self, symbol: str) -> BestBidAsk:
        return self._ask(
            GetBestBidAskQuery(venue=self._venue, symbol=symbol), BestBidAsk
        )

    def order_notional_limit(self) -> Decimal:
        return self._ask(GetOrderNotionalLimitQuery(venue=self._venue), Decimal)

    def _ask_unless_not_applicable[T](
        self, query: object, answer_type: type[T]
    ) -> T | NotApplicable:
        answer = self._dispatcher.dispatch(type(query), query)
        if answer is NotApplicable.ON_THIS_VENUE:
            return NotApplicable.ON_THIS_VENUE
        return _checked(query, answer, answer_type)

    def _ask[T](self, query: object, answer_type: type[T]) -> T:
        return _checked(
            query, self._dispatcher.dispatch(type(query), query), answer_type
        )


def _checked[T](query: object, answer: object, answer_type: type[T]) -> T:
    if not isinstance(answer, answer_type):
        raise TypeError(
            f"{type(query).__name__} was not answered with {answer_type.__name__} "
            f"but with {type(answer).__name__} — a handler is not bound"
        )
    return answer
