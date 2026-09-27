from enum import Enum

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType


class TradingVenue(str, Enum):
    """
    @brief Domain Value Object for where a submitted order goes (`EPIC-021A`).
    @details Deliberately has no `MAINNET` member. `EPIC-021`'s ADR §3: real-
    money trading is not a configuration flip, it is a future epic that has
    to add a new member here — the review that member would draw is the
    safety mechanism, not a runtime flag someone could toggle in
    `app_config.json`. `BOT-008` (live trading) stays unopened until then.
    """

    DISABLED = "disabled"
    FUTURES_TESTNET = "futures_testnet"
    SPOT_TESTNET = "spot_testnet"

    @property
    def market_type(self) -> MarketType | None:
        """@brief The market this venue trades, or `None` when trading is off."""
        if self is TradingVenue.FUTURES_TESTNET:
            return MarketType.FUTURES_USD_M
        if self is TradingVenue.SPOT_TESTNET:
            return MarketType.SPOT
        return None

    @property
    def supports_order_submission(self) -> bool:
        """@brief Whether this build's composition root has a real
        `ITradingClient`/`ITradingAccountReader`/`IUserDataStream`
        implementation for this venue.

        @details Distinct from "is this a closed, reviewed `TradingVenue`
        member" — both tradeable members now have one: `FUTURES_TESTNET`
        since `EPIC-021`, `SPOT_TESTNET` since `EPIC-027K` bound
        `SpotTradingClientFactory` alongside `FuturesTradingClientFactory` in
        `adapter_bindings.py`. The three order-path safety gates and
        `TradingModule`'s `ITradingClient` bind read this property, not a
        literal venue comparison, so a future venue only ever needs one line
        added here.
        """
        return self in (TradingVenue.FUTURES_TESTNET, TradingVenue.SPOT_TESTNET)
