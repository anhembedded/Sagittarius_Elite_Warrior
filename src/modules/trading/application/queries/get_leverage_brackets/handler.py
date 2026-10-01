"""`EPIC-028O` — `GetLeverageBracketsQueryHandler`: the addressed venue's
account control reads the brackets. A venue with no account control (Spot)
answers `NotApplicable.ON_THIS_VENUE`."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_leverage_brackets.query import (
    GetLeverageBracketsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)

logger = logging.getLogger("App.QueryHandler")


class GetLeverageBracketsQueryHandler(
    IQueryHandler[GetLeverageBracketsQuery, LeverageBrackets | NotApplicable]
):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(
        self, query: GetLeverageBracketsQuery
    ) -> LeverageBrackets | NotApplicable:
        source = self._contexts.get(query.venue).account_control
        if source is None:
            logger.debug(
                "GetLeverageBracketsQuery for %s on %s: the venue has no leverage brackets",
                query.symbol,
                query.venue.value,
            )
            return NotApplicable.ON_THIS_VENUE
        logger.debug(
            "Handling GetLeverageBracketsQuery for %s on %s",
            query.symbol,
            query.venue.value,
        )
        return source.leverage_brackets(query.symbol)
