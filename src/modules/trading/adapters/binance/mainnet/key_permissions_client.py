"""`EPIC-034` D5 — the one call the key gate makes: what the key may do.

@details `GET /sapi/v1/account/apiRestrictions` answers for the key whichever
market it trades, so a Futures mainnet venue asks the same endpoint through the
client of its own venue. A structural port because the implementer is
python-binance's `Client` (`architecture-rule.md` §2.1): it lists the one read the
gate uses, and the gate cannot reach anything else through it.
"""

from __future__ import annotations

from typing import Any, Protocol, cast

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.binance_client_builder import (
    new_client,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class IKeyPermissionsClient(Protocol):
    def get_account_api_permissions(self) -> dict[str, Any]: ...


def open_key_permissions_client(
    venue: TradingVenue, credentials: ExchangeCredentials
) -> IKeyPermissionsClient:
    """A signed session of `venue`, typed to the one read the gate makes."""
    return cast(IKeyPermissionsClient, new_client(venue, credentials))
