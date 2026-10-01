"""`EPIC-028H` — `OrderEntryTermsService` reads a symbol's rules and fees
through two queries addressed to its own venue."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.order_entry_terms_service import (
    OrderEntryTermsService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_commission_rate import (
    GetCommissionRateQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_symbol_order_rules import (
    GetSymbolOrderRulesQuery,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from ...ui.desk.order_entry_fixtures import TERMS

_SPOT = TradingVenue.SPOT_TESTNET


class _AnsweringDispatcher(ICommandDispatcher):
    def __init__(self, answers: dict[type, object]) -> None:
        self._answers = answers
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.dispatched.append(input_dto)
        return self._answers.get(handler_class)


def test_both_reads_are_addressed_to_the_services_venue() -> None:
    dispatcher = _AnsweringDispatcher(
        {
            GetSymbolOrderRulesQuery: TERMS.rules,
            GetCommissionRateQuery: TERMS.commission,
        }
    )

    terms = OrderEntryTermsService(dispatcher, _SPOT).terms_for("BTCUSDT")

    assert terms == TERMS
    assert dispatcher.dispatched == [
        GetSymbolOrderRulesQuery(venue=_SPOT, symbol="BTCUSDT"),
        GetCommissionRateQuery(venue=_SPOT, symbol="BTCUSDT"),
    ]


def test_an_unbound_handler_is_named_rather_than_answered() -> None:
    dispatcher = _AnsweringDispatcher({GetSymbolOrderRulesQuery: TERMS.rules})

    with pytest.raises(TypeError, match="not bound"):
        OrderEntryTermsService(dispatcher, _SPOT).terms_for("BTCUSDT")
