from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_request import (
    MANUAL_OWNER,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class ChangeMarginTypeCommand:
    """@brief Command to set a Futures symbol's margin mode, cross or
    isolated (`EPIC-028F`)."""

    symbol: str
    margin_type: MarginType
    #: `EPIC-028B` (ADR D3) — keyword-only and required.
    venue: TradingVenue = field(kw_only=True)
    #: Who asks (`EPIC-039H`): the symbol's lease holder may change its own symbol's settings,
    #: anyone else is refused while it is leased. The unprivileged default is a human at a form.
    owner_id: str = field(default=MANUAL_OWNER, kw_only=True)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
