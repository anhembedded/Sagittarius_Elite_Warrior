from enum import Enum

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


class TradingVenue(str, Enum):
    """
    @brief Domain Value Object for where a submitted order goes (`EPIC-021A`).
    @details Four places an order can go: Futures and Spot, each on the
    exchange's testnet and on mainnet. A mainnet venue is the same code as its
    testnet twin with one difference passed in, `testnet=False`, and its own
    key (`EPIC-034` D11, the owner's decision of 2026-10-07: mainnet trades
    exactly like testnet, no order is blocked, the owner accepts the risk). It
    supersedes `EPIC-021`'s ADR §3 and `EPIC-026` D3, which kept mainnet out of
    this enum so that adding it would be a reviewed change; these members are
    that change. What a mainnet venue adds is not a block: its key is refused
    if it can withdraw (D5), the secret lives in the OS keyring (D10), and the
    first order of a session asks one confirmation that names real money
    (`EPIC-034` D3).

    Declaration order is the order venues are listed, and the first one is the
    primary: the testnets come first, so a build with mainnet keys never makes
    a mainnet venue the default.
    """

    DISABLED = "disabled"
    FUTURES_TESTNET = "futures_testnet"
    SPOT_TESTNET = "spot_testnet"
    FUTURES_MAINNET = "futures_mainnet"
    SPOT_MAINNET = "spot_mainnet"

    @property
    def display_name(self) -> str:
        """@brief The venue as a person reads it ("Spot Testnet"); `value` is
        an identifier, never display text (`EPIC-034A`)."""
        return _TITLES[self]

    @property
    def market_type(self) -> MarketType | None:
        """@brief The market this venue trades, or `None` when trading is off."""
        if self in _FUTURES:
            return MarketType.FUTURES_USD_M
        if self in _SPOT:
            return MarketType.SPOT
        return None

    @property
    def market_data_venue(self) -> MarketDataVenue:
        """@brief The environment this venue's chart, stream and backtests read
        (`BUG-172`): the market its orders fill in, so the price shown is the
        price that fills. Both mainnet venues read the public mainnet.

        @raise ValueError this venue places no orders (`DISABLED`) and has no market.
        """
        try:
            return _MARKET_DATA_VENUES[self]
        except KeyError:
            raise ValueError(f"{self.value} trades no market to read") from None

    @property
    def is_mainnet(self) -> bool:
        """@brief Whether an order here moves real money."""
        return self in (TradingVenue.FUTURES_MAINNET, TradingVenue.SPOT_MAINNET)

    @property
    def is_testnet(self) -> bool:
        """@brief The `testnet` flag `python-binance`'s `Client` is built with
        for this venue."""
        return self in (TradingVenue.FUTURES_TESTNET, TradingVenue.SPOT_TESTNET)

    @property
    def supports_order_submission(self) -> bool:
        """@brief Whether this build's composition root has a real
        `ITradingClient`/`ITradingAccountReader`/`IUserDataStream`
        implementation for this venue.

        @details Every member but `DISABLED` has one, built by the same
        `VenueAssembly` path (`EPIC-028A`). The three order-path safety gates
        and `TradingModule`'s `ITradingClient` bind read this property, not a
        literal venue comparison, so a future venue only ever needs one line
        added here.
        """
        return self is not TradingVenue.DISABLED

    @property
    def has_positions(self) -> bool:
        """@brief Whether this venue has positions at all — `BUG-142`.

        @details Futures does; Spot holds balances and has nothing a "position
        limit" could count. Asked by the order path, rather than comparing the
        venue to a Spot member, so a position-shaped limit or piece of state
        reads one capability and a future venue sets it in one place.
        """
        return self in _FUTURES


_FUTURES = (TradingVenue.FUTURES_TESTNET, TradingVenue.FUTURES_MAINNET)
_SPOT = (TradingVenue.SPOT_TESTNET, TradingVenue.SPOT_MAINNET)

_MARKET_DATA_VENUES = {
    TradingVenue.FUTURES_TESTNET: MarketDataVenue.FUTURES_TESTNET,
    TradingVenue.SPOT_TESTNET: MarketDataVenue.SPOT_TESTNET,
    TradingVenue.FUTURES_MAINNET: MarketDataVenue.MAINNET_PUBLIC,
    TradingVenue.SPOT_MAINNET: MarketDataVenue.MAINNET_PUBLIC,
}

_TITLES = {
    TradingVenue.DISABLED: "Trading off",
    TradingVenue.FUTURES_TESTNET: "Futures Testnet",
    TradingVenue.SPOT_TESTNET: "Spot Testnet",
    TradingVenue.FUTURES_MAINNET: "Futures Mainnet",
    TradingVenue.SPOT_MAINNET: "Spot Mainnet",
}
