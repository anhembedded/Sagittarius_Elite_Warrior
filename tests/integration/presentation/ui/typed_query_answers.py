"""The queries `app_engine`'s dispatcher answers with a real value, not a `_FakeResponse`.

Each is a query whose real handler reaches outside this offscreen suite, or one a
background publisher sends that no test in the suite writes. The answer is built
from the real type, so a reader that calls a member of it gets the member
(`BUG-201`: the health snapshot's `bots` section calls `state_counts()` on a
`BotStatusReport`, which a `_FakeResponse` does not have).

Retire when: `app_engine` stops replacing the dispatcher's `dispatch`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_venue_choices import (
    GetVenueChoicesQuery,
    VenueChoices,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions import (
    GetOpenPositionsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.list_venue_keys import (
    ListVenueKeysQuery,
)

#: `GetOpenPositionsQuery` builds a real `FuturesTradingClient` and hits the network;
#: `ListVenueKeysQuery` (`BUG-176`, the Options page) reads the machine's own
#: `secrets.local.json` and keyring. Callers want a real tuple back, not a round
#: trip, so "no open position / no venue has a key" is the answer. A
#: `GetBotStatusReportQuery` is answered by the report of an app with no bot file:
#: this suite starts no bot. `GetVenueChoicesQuery` (`EPIC-048B`) reads each venue's stored key,
#: and the Bots screen raises on an answer that is not `VenueChoices`: no venue is offered here.
TYPED_QUERY_ANSWERS: dict[type, object] = {
    GetOpenPositionsQuery: (),
    ListVenueKeysQuery: (),
    GetBotStatusReportQuery: BotStatusReport(),
    GetVenueChoicesQuery: VenueChoices(),
}
