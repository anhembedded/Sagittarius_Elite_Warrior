from enum import Enum


class CommissionType(str, Enum):
    """
    @brief Commission calculation models supported by broker simulation (BOT-104).
    """

    PERCENT = "percent"  #: Percentage of trade notional value (e.g. 0.1% = 0.001)
    CASH_PER_ORDER = (
        "cash_per_order"  #: Fixed currency fee per executed order (e.g. $1.00)
    )
    CASH_PER_CONTRACT = "cash_per_contract"  #: Fixed currency fee per executed contract/coin unit (e.g. $0.05 / BTC)
