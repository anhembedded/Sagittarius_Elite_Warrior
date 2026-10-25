"""`EPIC-048B` — "what is left before this bot starts, or resumes, given these facts"."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.connection_read import (
    ConnectionRead,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_facts import (
    ExchangeChecking,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.futures_facts import (
    VenueSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_facts import BotRunFacts


@dataclass(frozen=True, slots=True)
class AssessBotQuery:
    """The facts a screen holds about one bot, and the parameters it judges.

    Every field but `config` is a read the screen already holds; `config` is the parameters on
    screen (the edited ones while the user edits). The query reads nothing: its handler is a pure
    function of these fields.
    """

    bot: BotSnapshot
    #: `None` when no kind in the catalog has the bot's `kind_id`. The kind is code, the same on
    #: either side of a link (`EPIC-048` D2), so it travels as itself.
    kind: IBotKind | None
    config: Mapping[str, str]
    connection: ConnectionRead
    #: `None` while the market numbers are being read.
    market: PlannerMarket | None
    #: The host's Run facts (`GetBotRunFactsQuery`); `None` while they are being read.
    run: BotRunFacts | None
    #: What the exchange says (`BOT-174`); still being asked until it answers.
    exchange: VenueSnapshot = field(default_factory=ExchangeChecking)
