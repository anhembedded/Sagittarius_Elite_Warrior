"""`EPIC-047A` — the types of the Bots screen's reads that cross the remote link, each under its wire name.

One entry per root; the records reachable from a root cross with it. The 14 roots are the
results of the queries the Bots screen reads (`BotList`, `BotFills`, `BotReadiness`,
`BotRunFacts`, `VenueSnapshot`, `PlanRiskRead`, `PlannerMarket`, the venue connection), the
bot itself, the command's result and the host-control request and reply.

Left out on purpose: `BotAssessment` and `AssessBotQuery` (the pure assessment runs on the
desktop, `EPIC-047` D1, so neither crosses) and `BotStatusReport` (read by the command line
only). `GetVenueChoicesQuery` joins when `EPIC-048B`'s second pull request makes it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.core.contracts.wire_root import WireRoot
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    BotList,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_fills import (
    BotFills,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.connection_read import (
    ConnectionRead,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.plan_risk_read import (
    PlanRiskRead,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_facts import BotRunFacts
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    VenueAccountSnapshot,
)

BOTS_WIRE_ROOTS: tuple[WireRoot, ...] = (
    WireRoot("sew.bot-snapshot/1", BotSnapshot),
    WireRoot("sew.bot-list/1", BotList),
    WireRoot("sew.bot-fills/1", BotFills),
    WireRoot("sew.bot-readiness/1", BotReadiness),
    WireRoot("sew.bot-run-facts/1", BotRunFacts),
    WireRoot("sew.bot-command-result/1", BotCommandResult),
    WireRoot("sew.exchange-facts/1", ExchangeFacts),
    WireRoot("sew.venue-snapshot/1", VenueSnapshot),
    WireRoot("sew.plan-risk-read/1", PlanRiskRead),
    WireRoot("sew.planner-market/1", PlannerMarket),
    WireRoot("sew.venue-connection/1", VenueAccountSnapshot | ConnectFailure),
    WireRoot("sew.connection-read/1", ConnectionRead),
    WireRoot("sew.host-control-request/1", HostControlRequest),
    WireRoot("sew.host-control-reply/1", HostControlReply),
)
