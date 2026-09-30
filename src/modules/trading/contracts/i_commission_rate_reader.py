"""`EPIC-028F` — reads the maker and taker rates one venue charges.

@details Both desks show an order's fee before it is sent (`EPIC-028G`), and
the fee depends on the account's tier, so it is read, not assumed. Futures
answers per symbol (`GET /fapi/v1/commissionRate`). Spot answers per account
(`GET /api/v3/account`'s `commissionRates`): the per-symbol
`/api/v3/account/commission` endpoint is not wrapped by the pinned
`python-binance`, and a symbol-specific discount is therefore not seen.

Plausible extensions, each one implementation behind this port: the Spot
per-symbol endpoint once the SDK wraps it; a caching decorator (rates change
with the monthly VIP tier, not per order); a COIN-M reader.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)


class ICommissionRateReader(ABC):
    """One venue's commission rates, read from the exchange."""

    @abstractmethod
    def commission_rate(self, symbol: str) -> CommissionRate:
        """@brief The maker and taker rates for an order on `symbol`.
        @throws CommissionRateUnavailableError The exchange did not answer."""
