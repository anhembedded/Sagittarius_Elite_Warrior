from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: The highest leverage Binance offers on any USD-M symbol. A symbol's own
#: ceiling is lower and depends on the position size; the exchange answers
#: that one (`AccountControlRefusal.EXCHANGE_REJECTED`).
MAX_LEVERAGE = 125


@dataclass(frozen=True)
class ChangeLeverageCommand:
    """@brief Command to set a Futures symbol's initial leverage
    (`EPIC-028F`)."""

    symbol: str
    leverage: int
    #: `EPIC-028B` (ADR D3) — keyword-only and required.
    venue: TradingVenue = field(kw_only=True)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not 1 <= self.leverage <= MAX_LEVERAGE:
            raise ValueError(
                f"leverage must be 1 to {MAX_LEVERAGE}, got {self.leverage}"
            )
