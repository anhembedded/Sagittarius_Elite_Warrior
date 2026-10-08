"""`EPIC-029E` — what every step of a running Grid works with.

One bundle per running bot, built by the executor factory: the bot's record
and its one writer (`BotRunState`), its way to trading (`BotOrderGateway` and
the venue's session), and the numbers its orders are held to.

The numbers are read **on first use, on the worker** (`LazyExchangeTerms`):
reading a symbol's filters can reach the network, and an executor is built at
start-up for every restored bot, where D12 allows no network and no order.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    BotOrderGateway,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_run_state import (
    BotRunState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_price_age import (
    GridPriceAge,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_reference_price import (
    GridReferencePrice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.off_ladder_orders import (
    OffLadderOrders,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
)


class LazyExchangeTerms:
    """The terms, read once when first asked for, and again on `refresh`."""

    def __init__(
        self,
        read: Callable[[], ExchangeTerms],
        read_fresh: Callable[[], ExchangeTerms],
    ) -> None:
        """@param read The terms as the venue's cached catalog has them.
        @param read_fresh The terms asked of the exchange again (`EPIC-035U`)."""
        self._read = read
        self._read_fresh = read_fresh
        self._terms: ExchangeTerms | None = None

    def get(self) -> ExchangeTerms:
        if self._terms is None:
            self._terms = self._read()
        return self._terms

    def refresh(self) -> None:
        """Ask the exchange for the terms again, replacing the kept ones
        (`EPIC-035E`: the symbol's status is read at each Start and Resume, not
        once per run; `EPIC-035U`: not from the venue's day-old catalog)."""
        self._terms = self._read_fresh()


@dataclass(frozen=True, slots=True)
class GridRunContext:
    """One running Grid's collaborators."""

    state: BotRunState
    gateway: BotOrderGateway
    session: ITradingSession
    params: GridParams
    terms_source: LazyExchangeTerms
    caps: OwnerBudgetCaps
    #: How long the bot has gone without hearing its price (`EPIC-035A`).
    price_age: GridPriceAge
    #: The price the bot acts on, with the moment it was heard (`EPIC-035J`).
    reference_price: GridReferencePrice
    #: The clock a bot's own intervals are measured on (`EPIC-035F`).
    monotonic: IMonotonicClock
    #: The run's orders no level holds whose fills still count.
    off_ladder: OffLadderOrders = field(default_factory=OffLadderOrders)

    @property
    def terms(self) -> ExchangeTerms:
        return self.terms_source.get()

    @property
    def base_asset(self) -> str:
        """The asset the bot buys and sells: its symbol less the quote."""
        return self.state.bot.definition.symbol.removesuffix(BUDGET_QUOTE_ASSET)

    @property
    def cap(self) -> Decimal:
        """The per-order notional cap every market slice stays under (D21)."""
        return self.terms.max_notional_per_order
