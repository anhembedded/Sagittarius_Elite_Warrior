"""`EPIC-034D` — where an account is read from: one per trading venue.

@details Since `EPIC-034` D11 an account can be read from exactly the places an
order can go, so each source is one `TradingVenue` and the two enums move
together. The source stays its own type because the Connect step reads *an
account*, never sends an order, and its snapshots and failures name where they
came from without carrying the venue's trading vocabulary. Before D11 there was
a fifth, read-only mainnet source with no venue (`EPIC-034E`); the owner removed
it with the rule it served ("mainnet trades exactly like testnet").

Plausible extensions, each one new member plus its venue: a second testnet
account; Spot Margin. The venue's own `VenueAssembly` serves it.
"""

from __future__ import annotations

from enum import Enum

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class AccountSource(str, Enum):
    FUTURES_TESTNET = "futures_testnet"
    SPOT_TESTNET = "spot_testnet"
    FUTURES_MAINNET = "futures_mainnet"
    SPOT_MAINNET = "spot_mainnet"

    @classmethod
    def for_venue(cls, venue: TradingVenue) -> AccountSource:
        """The source of the account `venue` trades on.
        @raise ValueError `venue` is `DISABLED`: it trades nowhere."""
        for source, trading_venue in _TRADING_VENUES.items():
            if trading_venue is venue:
                return source
        raise ValueError(f"{venue.name} has no account to read")

    @property
    def venue_title(self) -> str:
        """What the user is told: never the identifier."""
        return self.trading_venue.display_name

    @property
    def trading_venue(self) -> TradingVenue:
        """The venue orders for this account go to."""
        return _TRADING_VENUES[self]


_TRADING_VENUES: dict[AccountSource, TradingVenue] = {
    AccountSource.FUTURES_TESTNET: TradingVenue.FUTURES_TESTNET,
    AccountSource.SPOT_TESTNET: TradingVenue.SPOT_TESTNET,
    AccountSource.FUTURES_MAINNET: TradingVenue.FUTURES_MAINNET,
    AccountSource.SPOT_MAINNET: TradingVenue.SPOT_MAINNET,
}
