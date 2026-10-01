"""`EPIC-028O` — `GetFuturesSymbolSettingQueryHandler`: the addressed
venue's account control reads the setting. A venue with no account control
(Spot) answers `NotApplicable.ON_THIS_VENUE`, never an invented leverage."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_futures_symbol_setting.query import (
    GetFuturesSymbolSettingQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.not_applicable import (
    NotApplicable,
)

logger = logging.getLogger("App.QueryHandler")


class GetFuturesSymbolSettingQueryHandler(
    IQueryHandler[GetFuturesSymbolSettingQuery, FuturesSymbolSetting | NotApplicable]
):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(
        self, query: GetFuturesSymbolSettingQuery
    ) -> FuturesSymbolSetting | NotApplicable:
        source = self._contexts.get(query.venue).account_control
        if source is None:
            logger.debug(
                "GetFuturesSymbolSettingQuery for %s on %s: the venue has no leverage and margin mode",
                query.symbol,
                query.venue.value,
            )
            return NotApplicable.ON_THIS_VENUE
        logger.debug(
            "Handling GetFuturesSymbolSettingQuery for %s on %s",
            query.symbol,
            query.venue.value,
        )
        return source.symbol_setting(query.symbol)
