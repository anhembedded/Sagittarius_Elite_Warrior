"""`EPIC-034E` — the one `/sapi/` route the read-only mainnet account calls:

    GET    /sapi/v1/account/apiRestrictions   `get_account_api_permissions()`

Spot mainnet's wallet family (`Client.MARGIN_API_URL`). Anything else under
`/sapi/` 404s like every unknown path: the read-only source calls this route and
no other, and a route that placed or moved anything must not exist here.

The answer is whatever the test set on `ApiRestrictions`, so a test can hand the
app a key that can withdraw, one that can trade, and a read-only one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ApiRestrictions:
    """What the fake exchange says the key may do. Defaults to a read-only key."""

    enable_reading: bool = True
    enable_spot_and_margin_trading: bool = False
    enable_withdrawals: bool = False
    enable_margin: bool = False
    enable_futures: bool = False
    enable_internal_transfer: bool = False

    def payload(self) -> dict[str, object]:
        return {
            "ipRestrict": False,
            "createTime": 1698645219000,
            "enableReading": self.enable_reading,
            "enableWithdrawals": self.enable_withdrawals,
            "enableInternalTransfer": self.enable_internal_transfer,
            "enableMargin": self.enable_margin,
            "enableFutures": self.enable_futures,
            "permitsUniversalTransfer": False,
            "enableVanillaOptions": False,
            "enableFixApiTrade": False,
            "enableFixReadOnly": False,
            "enableSpotAndMarginTrading": self.enable_spot_and_margin_trading,
            "enablePortfolioMarginTrading": False,
        }


def handle(
    method: str, path: str, restrictions: ApiRestrictions
) -> tuple[int, object] | None:
    if method == "GET" and path == "/sapi/v1/account/apiRestrictions":
        return 200, restrictions.payload()
    return None
