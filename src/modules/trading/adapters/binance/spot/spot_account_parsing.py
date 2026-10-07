"""`EPIC-034E` — what a Spot `GET /api/v3/account` answer holds, read once.

@details Shared by `SpotAccountReader` (one class for Spot Testnet and Spot
Mainnet, `EPIC-034` D11) and the Spot commission reader, so the two read one
payload the same way. Pure functions over the payload.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)

#: Anything at or below this quantity is fee-dust, not a holding worth
#: pricing — eight decimal places is Binance's own finest representable
#: unit across the symbols this app trades.
DUST_THRESHOLD = Decimal("0.00000001")


def parse_holdings(account: dict[str, Any]) -> tuple[SpotHolding, ...]:
    holdings: list[SpotHolding] = []
    for balance in account.get("balances", []):
        try:
            free = Decimal(str(balance.get("free", "0")))
            locked = Decimal(str(balance.get("locked", "0")))
        except InvalidOperation:
            continue
        if free + locked <= 0:
            continue
        holdings.append(
            SpotHolding(
                asset=str(balance.get("asset", "")),
                free=free,
                locked=locked,
                dust_threshold=DUST_THRESHOLD,
            )
        )
    return tuple(holdings)


def parse_account_commission(account: dict[str, Any], symbol: str) -> CommissionRate:
    """The account's maker and taker rates (`commissionRates`, decimal
    strings), carried onto `symbol`.
    @throws KeyError The payload has no `commissionRates`.
    @throws InvalidOperation A rate is not a number."""
    rates = account["commissionRates"]
    return CommissionRate(
        symbol=symbol,
        maker=Decimal(str(rates["maker"])),
        taker=Decimal(str(rates["taker"])),
    )
