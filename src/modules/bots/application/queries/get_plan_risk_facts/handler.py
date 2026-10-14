"""`EPIC-039J` — handler for `GetPlanRiskFactsQuery`: the symbol's setting and leverage brackets.

The facts come through the one port every venue answers (`IVenueFacts`), so no market is named
here: a venue that carries no position risk answers a snapshot with no brackets and this says
so. A bot that cannot be found, or a snapshot that is not loaded, is an unavailable read in
words, never an empty set of brackets.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_plan_risk_facts.query import (
    GetPlanRiskFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
    ExchangeUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    FuturesLoaded,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_facts import (
    IVenueFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.plan_risk_read import (
    PlanRiskRead,
    PlanRiskUnavailable,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    PlanRiskFacts,
)

_NO_POSITION_RISK = "this venue carries no position risk"


class GetPlanRiskFactsQueryHandler(IQueryHandler[GetPlanRiskFactsQuery, PlanRiskRead]):
    def __init__(self, store: IBotStore, facts: IVenueFacts) -> None:
        self._lookup = BotLookup(store)
        self._facts = facts

    def execute(self, query: GetPlanRiskFactsQuery) -> PlanRiskRead:
        found = self._lookup.find(query.bot_id)
        if isinstance(found, BotCommandResult):
            return PlanRiskUnavailable(found.message)
        snapshot = self._facts.read(found.bot)
        if isinstance(snapshot, FuturesLoaded):
            return PlanRiskFacts(snapshot.facts.symbol_setting, snapshot.facts.brackets)
        if isinstance(snapshot, ExchangeUnavailable):
            return PlanRiskUnavailable(snapshot.reason)
        if isinstance(snapshot, ExchangeChecking):
            return PlanRiskUnavailable("the venue's facts are still being read")
        return PlanRiskUnavailable(_NO_POSITION_RISK)
