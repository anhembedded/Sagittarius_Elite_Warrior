"""`EPIC-028H` — `GetSymbolOrderRulesQueryHandler`: the addressed venue's own
metadata provider answers, from its cache or a catalog fetch. The same
provider `PreviewOrderQueryHandler` rounds every order with, so a panel's
sizing and the submitted order agree."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_symbol_order_rules.query import (
    GetSymbolOrderRulesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_rules_unavailable_error import (
    SymbolRulesUnavailableError,
)

logger = logging.getLogger("App.QueryHandler")


class GetSymbolOrderRulesQueryHandler(
    IQueryHandler[GetSymbolOrderRulesQuery, SymbolOrderMetadata]
):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetSymbolOrderRulesQuery) -> SymbolOrderMetadata:
        logger.debug(
            "Handling GetSymbolOrderRulesQuery for %s on %s",
            query.symbol,
            query.venue.value,
        )
        provider = self._contexts.get(query.venue).metadata_provider
        rules = provider.get_or_fetch(query.symbol)
        if rules is None:
            raise SymbolRulesUnavailableError(
                f"{query.venue.value} does not list {query.symbol}"
            )
        return rules
