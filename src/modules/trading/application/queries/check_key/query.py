from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)


@dataclass(frozen=True)
class CheckKeyQuery:
    """@brief Which venues a Binance key is for, kept nowhere (`BOT-200`).

    @details `credentials` prints masked, but a query that is logged would still show
    the key's first and last four characters, so nothing logs this one.
    """

    credentials: ExchangeCredentials
