from dataclasses import dataclass
from enum import Enum

_MAX_PERCENT = 100.0


class PositionSizingType(str, Enum):
    """
    @brief Supported modes for determining order size in backtesting simulations (BOT-104).
    """

    PERCENT_OF_EQUITY = "percent_of_equity"  #: Allocates a percentage of current total account equity (e.g. 20.0%)
    FIXED_CASH = (
        "fixed_cash"  #: Deploys a fixed currency amount per order (e.g. 1000.0 USD)
    )
    FIXED_CONTRACTS = "fixed_contracts"  #: Deploys a fixed coin/contract quantity per order (e.g. 0.5 BTC)
    #: BOT-041 — sizes so a stop-loss hit loses exactly `value`% of current
    #: equity, not a fixed capital allocation. Requires
    #: `BrokerSimulationConfig.stop_loss_pct` to be set (the stop distance is
    #: what turns a risk % into a quantity) — `PaperExchange` rejects entries
    #: when it isn't, rather than silently falling back to another sizing.
    RISK_PERCENT = "risk_percent"


@dataclass(frozen=True)
class PositionSizing:
    """
    @brief Immutable configuration for position sizing logic (BOT-104).
    """

    type: PositionSizingType = PositionSizingType.PERCENT_OF_EQUITY
    value: float = 100.0

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError(
                f"Position sizing value must be positive, got {self.value}"
            )
        if self.type is PositionSizingType.PERCENT_OF_EQUITY and (
            self.value > _MAX_PERCENT or self.value <= 0
        ):
            raise ValueError(
                f"Percent of equity sizing value must be in (0, 100], got {self.value}"
            )
        if self.type is PositionSizingType.RISK_PERCENT and (
            self.value > _MAX_PERCENT or self.value <= 0
        ):
            raise ValueError(
                f"Risk percent sizing value must be in (0, 100], got {self.value}"
            )
