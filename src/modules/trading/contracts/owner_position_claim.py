"""`BUG-250` — who says a position on the account is its own, and for which run.

@details The identity of an owner's run: its id, the client order tag its orders carry, the one
symbol it trades and when the run started. It carries **no figure**: trading derives the position
from the venue's history of the owner's tagged orders since `run_started_at`, so a bot's file that
claims more than the exchange shows changes nothing (`OwnerBudgetRegistration`, ADR D6). The claim
only says whose history to read. Opening a closed order session with claims excuses a position
that history explains (`PositionExplainer`); opening it with none refuses every position.

`OwnerBudgetRegistration` is a claim that also carries a budget, so the one derivation serves both.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    validate_client_order_tag,
)


@dataclass(frozen=True)
class OwnerPositionClaim:
    """An owner's run, named so its position can be derived from the venue's evidence."""

    owner_id: str
    #: The owner's client order tag (`client_order_id.py`); its orders carry it.
    tag: str
    symbol: str
    #: When the owner's current run started; executions before it are not the owner's.
    run_started_at: datetime

    def __post_init__(self) -> None:
        validate_client_order_tag(self.tag)
        if self.run_started_at.tzinfo is None:
            raise ValueError("run_started_at must be timezone-aware")
