"""The plan, as typed values (`EPIC-038I`).

A plan lists bots by what a person chooses - name, kind, venue, symbol, the kind's
parameters and whether the bot should run - and by nothing else. There is deliberately
**no field for a key, a secret or an account identifier**: a plan is committed to version
control and read by people, and the credentials live behind `IExchangeCredentialsProvider`.

The identity of an entry is its `name` plus its `venue`. Renaming is therefore a delete
and a create, and the diff says so.

@par The file
`{"schema": "sew.bot-plan/1", "bots": [{"name", "kind", "venue", "symbol", "params",
"desired_state"}]}`. `params` is what `CreateBotCommand.config` takes: text, so no float
touches a price. `desired_state` is `running` or `stopped`; `bot apply` records it and
`run --start-planned` starts the bots that want to run and are at rest. Applying never
starts or stops a bot itself.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: The file's version. A breaking change to the file is a new string.
SCHEMA = "sew.bot-plan/1"


@dataclass(frozen=True, slots=True)
class PlannedBot:
    name: str
    kind: str
    venue: TradingVenue
    symbol: str
    desired_state: DesiredState
    params: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))

    @property
    def identity(self) -> tuple[str, TradingVenue]:
        return (self.name, self.venue)


@dataclass(frozen=True, slots=True)
class BotPlanDocument:
    bots: tuple[PlannedBot, ...] = ()

    def to_json_text(self) -> str:
        """The plan as the file holds it: stable key order, two-space indent, a final newline."""
        document = {
            "schema": SCHEMA,
            "bots": [
                {
                    "name": bot.name,
                    "kind": bot.kind,
                    "venue": bot.venue.value,
                    "symbol": bot.symbol,
                    "params": dict(bot.params),
                    "desired_state": bot.desired_state.value,
                }
                for bot in self.bots
            ],
        }
        return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
