"""`EPIC-029E` — what every step of a running Grid works with.

One bundle per running bot, built by the executor factory: the bot's record
and its one writer (`BotRunState`), its way to trading (`BotOrderGateway` and
the venue's session), and the numbers its orders are held to.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    BotOrderGateway,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_run_state import (
    BotRunState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)


@dataclass(frozen=True, slots=True)
class GridRunContext:
    """One running Grid's collaborators."""

    state: BotRunState
    gateway: BotOrderGateway
    session: ITradingSession
    params: GridParams
    terms: ExchangeTerms
    caps: OwnerBudgetCaps

    @property
    def cap(self) -> Decimal:
        """The per-order notional cap every market slice stays under (D21)."""
        return self.terms.max_notional_per_order
