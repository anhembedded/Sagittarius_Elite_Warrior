"""`EPIC-034D` — where an account is read from, which is wider than where an
order may go.

@details A `TradingVenue` names a place an order can be sent, and it has no
mainnet member by design (`EPIC-026` D3). An account can be *read* from more
places than that: `EPIC-034E` adds a read-only mainnet source here, and only
here. Keeping the two enums apart is the point: a member of `AccountSource`
that is not a `TradingVenue` has no order path to reach, so the wrong state
cannot be written (`code/errors.md` #8).

Plausible extensions, each one new member plus its reader's registration: a
Futures mainnet read-only source; a second testnet account.
"""

from __future__ import annotations

from enum import Enum

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class AccountSource(str, Enum):
    FUTURES_TESTNET = "futures_testnet"
    SPOT_TESTNET = "spot_testnet"
    #: `EPIC-034E` — the owner's real Spot account, read and never traded. It
    #: has no `TradingVenue`: nothing that sends an order can be pointed at it.
    SPOT_MAINNET_READONLY = "spot_mainnet_readonly"

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
        return _TITLES[self]

    @property
    def trading_venue(self) -> TradingVenue | None:
        """The venue orders for this account go to, or `None` for a source
        that is read and never traded."""
        return _TRADING_VENUES[self]


_TITLES = {
    AccountSource.FUTURES_TESTNET: "Futures Testnet",
    AccountSource.SPOT_TESTNET: "Spot Testnet",
    AccountSource.SPOT_MAINNET_READONLY: "Mainnet · read only",
}

#: The venue each source's orders go to; a source mapped to `None` is read
#: and never traded (`EPIC-034E`).
_TRADING_VENUES: dict[AccountSource, TradingVenue | None] = {
    AccountSource.FUTURES_TESTNET: TradingVenue.FUTURES_TESTNET,
    AccountSource.SPOT_TESTNET: TradingVenue.SPOT_TESTNET,
    AccountSource.SPOT_MAINNET_READONLY: None,
}
