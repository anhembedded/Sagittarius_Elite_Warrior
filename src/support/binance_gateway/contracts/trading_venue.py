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
