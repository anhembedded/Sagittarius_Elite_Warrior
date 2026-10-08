"""`EPIC-028H` — `OrderEntryTermsService` reads a symbol's rules and fees
through two queries addressed to its own venue; `EPIC-028O` adds one query
per new read."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.order_entry_terms_service import (
    OrderEntryTermsService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_best_bid_ask import (
    GetBestBidAskQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_commission_rate import (
    GetCommissionRateQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_futures_symbol_setting import (
    GetFuturesSymbolSettingQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_leverage_brackets import (
    GetLeverageBracketsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_mark_price import (
    GetMarkPriceQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_notional_limit import (
    GetOrderNotionalLimitQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_symbol_order_rules import (
    GetSymbolOrderRulesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import MarkPrice
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
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


def test_a_fresh_read_asks_for_the_rules_again_and_the_fee_as_usual() -> None:
    """`EPIC-035U` — the same two queries, the rules one marked `refresh`."""
    dispatcher = _AnsweringDispatcher(
        {
            GetSymbolOrderRulesQuery: TERMS.rules,
            GetCommissionRateQuery: TERMS.commission,
        }
    )

    terms = OrderEntryTermsService(dispatcher, _SPOT).fresh_terms_for("BTCUSDT")

    assert terms == TERMS
    assert dispatcher.dispatched == [
        GetSymbolOrderRulesQuery(venue=_SPOT, symbol="BTCUSDT", refresh=True),
        GetCommissionRateQuery(venue=_SPOT, symbol="BTCUSDT"),
    ]


def test_an_unbound_handler_is_named_rather_than_answered() -> None:
    dispatcher = _AnsweringDispatcher({GetSymbolOrderRulesQuery: TERMS.rules})

    with pytest.raises(TypeError, match="not bound"):
        OrderEntryTermsService(dispatcher, _SPOT).terms_for("BTCUSDT")


_FUTURES = TradingVenue.FUTURES_TESTNET
_SETTING = FuturesSymbolSetting("BTCUSDT", 20, MarginType.CROSSED, Decimal(2_000_000))
_BRACKETS = LeverageBrackets(
    "BTCUSDT",
    (
        LeverageBracket(
            1, 125, Decimal(0), Decimal(50_000), Decimal("0.004"), Decimal(0)
        ),
    ),
)
_MARK = MarkPrice("BTCUSDT", Decimal(64000), datetime(2026, 10, 1, tzinfo=UTC))
_BOOK = BestBidAsk(
    "BTCUSDT", Decimal("63999.9"), Decimal(1), Decimal("64000.1"), Decimal(1)
)


def test_every_epic_028o_read_is_addressed_to_the_services_venue() -> None:
    """`EPIC-028O` — one query per read, each naming this service's venue."""
    dispatcher = _AnsweringDispatcher(
        {
            GetFuturesSymbolSettingQuery: _SETTING,
            GetLeverageBracketsQuery: _BRACKETS,
            GetMarkPriceQuery: _MARK,
            GetBestBidAskQuery: _BOOK,
            GetOrderNotionalLimitQuery: Decimal(500),
        }
    )
    service = OrderEntryTermsService(dispatcher, _FUTURES)

    answers = (
        service.futures_setting_for("BTCUSDT"),
        service.leverage_brackets_for("BTCUSDT"),
        service.mark_price_for("BTCUSDT"),
        service.best_bid_ask_for("BTCUSDT"),
        service.order_notional_limit(),
    )

    assert answers == (_SETTING, _BRACKETS, _MARK, _BOOK, Decimal(500))
    assert dispatcher.dispatched == [
        GetFuturesSymbolSettingQuery(venue=_FUTURES, symbol="BTCUSDT"),
        GetLeverageBracketsQuery(venue=_FUTURES, symbol="BTCUSDT"),
        GetMarkPriceQuery(venue=_FUTURES, symbol="BTCUSDT"),
        GetBestBidAskQuery(venue=_FUTURES, symbol="BTCUSDT"),
        GetOrderNotionalLimitQuery(venue=_FUTURES),
    ]


def test_spots_not_applicable_answers_pass_through_unchanged() -> None:
    not_applicable = NotApplicable.ON_THIS_VENUE
    dispatcher = _AnsweringDispatcher(
        {
            GetFuturesSymbolSettingQuery: not_applicable,
            GetLeverageBracketsQuery: not_applicable,
            GetMarkPriceQuery: not_applicable,
        }
    )
    service = OrderEntryTermsService(dispatcher, _SPOT)

    assert service.futures_setting_for("BTCUSDT") is not_applicable
    assert service.leverage_brackets_for("BTCUSDT") is not_applicable
    assert service.mark_price_for("BTCUSDT") is not_applicable


@pytest.mark.parametrize(
    "read",
    [
        lambda s: s.futures_setting_for("BTCUSDT"),
        lambda s: s.leverage_brackets_for("BTCUSDT"),
        lambda s: s.mark_price_for("BTCUSDT"),
        lambda s: s.best_bid_ask_for("BTCUSDT"),
        lambda s: s.order_notional_limit(),
    ],
    ids=["setting", "brackets", "mark", "book", "notional-limit"],
)
def test_an_unbound_read_names_its_query(read: object) -> None:
    service = OrderEntryTermsService(_AnsweringDispatcher({}), _FUTURES)

    with pytest.raises(
        TypeError, match="Query was not answered .* a handler is not bound"
    ):
        read(service)  # type: ignore[operator]
