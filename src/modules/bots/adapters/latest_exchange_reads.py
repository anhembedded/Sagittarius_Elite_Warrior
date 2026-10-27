"""`EPIC-047H` — `ILatestExchangeReads` in memory: one slot per bot (and per symbol's rules), under a lock."""

from __future__ import annotations

import threading
from collections.abc import Collection

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.exchange_reads import (
    BotFillsRead,
    BotPlannerRead,
    HostExchangeReads,
    SymbolRulesRead,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_latest_exchange_reads import (
    ILatestExchangeReads,
)


class LatestExchangeReads(ILatestExchangeReads):
    """Written by the refresher's worker and read by the facts writer's, so every access takes the lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._planner: dict[str, BotPlannerRead] = {}
        self._fills: dict[str, BotFillsRead] = {}
        self._rules: dict[tuple[str, str], SymbolRulesRead] = {}

    def record_planner(self, read: BotPlannerRead) -> None:
        with self._lock:
            self._planner[read.bot_id] = read

    def record_fills(self, read: BotFillsRead) -> None:
        with self._lock:
            self._fills[read.bot_id] = read

    def record_rules(self, read: SymbolRulesRead) -> None:
        with self._lock:
            self._rules[(read.venue.value, read.symbol)] = read

    def retain(self, bot_ids: Collection[str]) -> None:
        with self._lock:
            for held in (self._planner, self._fills):
                for gone in held.keys() - set(bot_ids):
                    del held[gone]

    def latest(self) -> HostExchangeReads:
        with self._lock:
            planner, fills, rules = (
                dict(self._planner),
                dict(self._fills),
                dict(self._rules),
            )
        return HostExchangeReads(
            planner=tuple(planner[key] for key in sorted(planner)),
            fills=tuple(fills[key] for key in sorted(fills)),
            symbol_rules=tuple(rules[key] for key in sorted(rules)),
        )
