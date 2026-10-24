"""`EPIC-048B` (DERISK R1, kept) — the Bots tab's detail built from reads that crossed a wire equals
the detail built in process.

The business promise of the doors (`architecture-rule.md` §3.1): every host fact the detail is
judged on reaches the screen through a query, and the judgement runs where the screen runs. So a
dispatcher that sends each host query by its type name, as bytes, to a host that answers with its
own handlers, and answers only the pure assessment locally, must give the screen the very same
`BotDetail` — readiness, verdicts, checks, availability, overlay and ladder — as the dispatcher in
process. A fact the screen read around the doors would be missing on the far side of the wire, and
the two details would differ.

The wire here is `pickle`, which keeps no object identity across it; `EPIC-047A` brings the link's
JSON codec, and `_over_the_wire` is the one place it goes.
"""

from __future__ import annotations

import copyreg
import io
import pickle
from types import MappingProxyType
from typing import Any

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.assess_bot import (
    AssessBotQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_run_facts import (
    GetBotRunFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_exchange_facts import (
    GetExchangeFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_plan_risk_facts import (
    GetPlanRiskFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_connection import (
    GetVenueConnectionQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_detail import (
    BotDetail,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.connect_view import (
    connected_view,
    connection_read,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)

from .bots_screen_fixtures import NOW, SYMBOL, BotsScreen, open_screen, stored

#: What the host answers, by the name a query crosses the wire with: the wire's allowlist.
_HOST_QUERIES = {
    query.__name__: query
    for query in (
        ListBotsQuery,
        GetPlannerMarketQuery,
        GetExchangeFactsQuery,
        GetPlanRiskFactsQuery,
        GetBotRunFactsQuery,
        GetVenueConnectionQuery,
    )
}
#: A lease only the host knows of: a manual order ticket on the Trade tab holds the symbol.
_HOST_ONLY_HOLDER = "manual:trade-tab"


def _read_only(mapping: dict[str, object]) -> MappingProxyType[str, object]:
    return MappingProxyType(mapping)


def _over_the_wire(payload: object) -> object:
    """`payload` as bytes and back. A read-only mapping crosses as the plain mapping it shows,
    rebuilt read-only on the far side (DERISK R4's trap: `MappingProxyType` has no wire form of
    its own)."""
    buffer = io.BytesIO()
    pickler = pickle.Pickler(buffer)
    pickler.dispatch_table = {
        **copyreg.dispatch_table,
        MappingProxyType: lambda proxy: (_read_only, (dict(proxy),)),
    }
    pickler.dump(payload)
    return pickle.loads(buffer.getvalue())  # noqa: S301 - the test's own bytes, both ends


class WireDispatcher(ICommandDispatcher):
    """Sends a host query by its name, as bytes, to the host's dispatcher; answers the pure
    assessment where the screen runs (`EPIC-048` D5). Any other query is refused, as a link
    refuses a name it does not know."""

    def __init__(self, host: ICommandDispatcher, local: ICommandDispatcher) -> None:
        self._host = host
        self._local = local
        self.sent: list[str] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> Any:
        if handler_class is AssessBotQuery:
            return self._local.dispatch(handler_class, input_dto)
        name = handler_class.__name__
        if name not in _HOST_QUERIES:
            raise AssertionError(f"{name} does not cross the wire")
        self.sent.append(name)
        request = _over_the_wire((name, input_dto))
        assert isinstance(request, tuple)
        query_name, query = request
        return _over_the_wire(self._host.dispatch(_HOST_QUERIES[query_name], query))


def _detail_through(commands: ICommandDispatcher, screen: BotsScreen) -> BotDetail:
    """The detail as the screen builds it: each fact read through `commands`, then judged."""
    listed = commands.dispatch(ListBotsQuery, ListBotsQuery())
    bot = listed.bots[0]
    selected = SelectedBot(screen.kinds, lambda: NOW, commands)
    selected.select(bot)
    selected.take_market(
        commands.dispatch(
            GetPlannerMarketQuery, GetPlannerMarketQuery(bot.venue, bot.symbol)
        )
    )
    selected.take_exchange(
        commands.dispatch(GetExchangeFactsQuery, GetExchangeFactsQuery(bot.bot_id))
    )
    selected.take_risk(
        commands.dispatch(GetPlanRiskFactsQuery, GetPlanRiskFactsQuery(bot.bot_id))
    )
    answer = commands.dispatch(
        GetVenueConnectionQuery, GetVenueConnectionQuery(bot.venue, bot.symbol)
    )
    assert isinstance(answer, VenueAccountSnapshot)
    selected.connection = connection_read(connected_view(answer), answer)
    detail = selected.detail()
    assert detail is not None
    return detail


def test_the_detail_through_the_wire_equals_the_detail_in_process(
    tmp_path, qtbot
) -> None:
    screen = open_screen(
        tmp_path, qtbot, bots=[stored("a00001", S.DRAFT), stored("b00002", S.PAUSED)]
    )
    screen.trading_session.claim_symbol(SYMBOL, _HOST_ONLY_HOLDER)
    wire = WireDispatcher(screen.dispatcher, screen.dispatcher)

    through_the_wire = _detail_through(wire, screen)

    assert through_the_wire == _detail_through(screen.dispatcher, screen)
    assert through_the_wire.readiness is not None
    assert _HOST_ONLY_HOLDER in through_the_wire.readiness.message()
    assert "b00002" in through_the_wire.readiness.message()
    assert set(wire.sent) == set(_HOST_QUERIES)
    screen.presenter.shutdown()
