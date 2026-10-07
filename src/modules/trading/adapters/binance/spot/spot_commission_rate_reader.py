"""`EPIC-028F` — `ICommissionRateReader` for Spot.

@details `GET /api/v3/account` carries `commissionRates: {maker, taker,
buyer, seller}` as decimal strings (`"0.00100000"` is 0.1 %). These are the
account's rates. The per-symbol `GET /api/v3/account/commission` is in the
installed `python-binance` 1.0.37 only as the auto-generated
`v3_get_account_commission`, which this reader does not call, so a
symbol-specific discount is not seen (the port's docstring names reading it
as an extension; `EPIC-028Q` corrected the claim that it was missing). The symbol is
carried into the answer only. Payload shape per Binance's documented Spot
API, with the same live-call disclosure as `spot_account_reader.py`.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    describe_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate_unavailable_error import (
    CommissionRateUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_commission_rate_reader import (
    ICommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_spot_session_factory import (
    ISpotSessionFactory,
)

#: What a commission read can raise from the SDK, the network or a malformed
#: payload.
_READ_FAILURES = (
    BinanceAPIException,
    BinanceRequestException,
    RequestException,
    KeyError,
    TypeError,
    InvalidOperation,
)


class SpotCommissionRateReader(ICommissionRateReader):
    """Reads one Spot account's commission rates."""

    def __init__(
        self,
        session_factory: ISpotSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider

    def commission_rate(self, symbol: str) -> CommissionRate:
        credentials = self._credentials_provider.resolve().credentials
        if credentials is None:
            raise CommissionRateUnavailableError(
                f"{symbol}: no Spot credentials configured"
            )
        try:
            client = self._session_factory.create_account_client(credentials)
            account: dict[str, Any] = client.get_account()
            rates = account["commissionRates"]
            return CommissionRate(
                symbol=symbol,
                maker=Decimal(str(rates["maker"])),
                taker=Decimal(str(rates["taker"])),
            )
        except _READ_FAILURES as exc:
            raise CommissionRateUnavailableError(
                f"{symbol} Spot commission rate could not be read: {describe_failure(exc, repr)}"
            ) from exc
