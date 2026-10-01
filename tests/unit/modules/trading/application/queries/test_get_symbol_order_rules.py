"""`EPIC-028H` — `GetSymbolOrderRulesQuery` answers from the addressed
venue's own metadata provider, and refuses a symbol it does not list."""

from __future__ import annotations

from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_symbol_order_rules import (
    GetSymbolOrderRulesQuery,
    GetSymbolOrderRulesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_market_metadata_provider import (
    FakeMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from ...ui.desk.order_entry_fixtures import TERMS

_SPOT = TradingVenue.SPOT_TESTNET
_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT_RULES = TERMS.rules
_FUTURES_RULES = replace(TERMS.rules, step_size=TERMS.rules.step_size * 10)


def _handler() -> GetSymbolOrderRulesQueryHandler:
    return GetSymbolOrderRulesQueryHandler(
        FakeVenueContexts(
            fake_venue_context(
                _FUTURES, metadata_provider=FakeMarketMetadataProvider([_FUTURES_RULES])
            ),
            fake_venue_context(
                _SPOT, metadata_provider=FakeMarketMetadataProvider([_SPOT_RULES])
            ),
        )
    )


def test_each_venue_answers_with_its_own_rules() -> None:
    handler = _handler()

    spot = handler.execute(GetSymbolOrderRulesQuery(venue=_SPOT, symbol="BTCUSDT"))
    futures = handler.execute(
        GetSymbolOrderRulesQuery(venue=_FUTURES, symbol="BTCUSDT")
    )

    assert spot == _SPOT_RULES
    assert futures == _FUTURES_RULES


def test_a_symbol_the_venue_does_not_list_is_refused_by_name() -> None:
    with pytest.raises(SymbolRulesUnavailableError, match="NOPEUSDT"):
        _handler().execute(GetSymbolOrderRulesQuery(venue=_SPOT, symbol="NOPEUSDT"))


def test_an_empty_symbol_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="symbol"):
        GetSymbolOrderRulesQuery(venue=_SPOT, symbol="")
