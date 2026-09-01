from enum import Enum


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
