"""`EPIC-028F` — reads the maker and taker rates one venue charges.

@details Both desks show an order's fee before it is sent (`EPIC-028G`), and
the fee depends on the account's tier, so it is read, not assumed. Futures
answers per symbol (`GET /fapi/v1/commissionRate`). Spot answers per account
(`GET /api/v3/account`'s `commissionRates`), so a symbol-specific discount
is not seen. The per-symbol `GET /api/v3/account/commission` is in the
pinned `python-binance` only as the auto-generated
`v3_get_account_commission` (`EPIC-028Q` corrected an earlier "not wrapped").

Plausible extensions, each one implementation behind this port: a Spot
reader calling that per-symbol endpoint; a caching decorator (rates change
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
