"""`EPIC-040D` — "replay this request with the backtester of this kind of bot"."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_kind_backtester import (
    KindBacktestRequest,
)


@dataclass(frozen=True, slots=True)
class RunBacktestQuery:
    """A kind-neutral backtest: the kind's id and the request every kind answers
    (`KindBacktestRequest`, with its `cancelled` poll, `async-ui-action-rule.md`)."""

    kind_id: str
    request: KindBacktestRequest
