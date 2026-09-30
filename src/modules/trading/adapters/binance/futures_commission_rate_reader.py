"""`EPIC-028F` — `ICommissionRateReader` for USD-M Futures.

@details `GET /fapi/v1/commissionRate?symbol=` answers `{symbol,
makerCommissionRate, takerCommissionRate}` as decimal strings (`"0.0002"` is
0.02 %). Payload shape per Binance's documented USD-M API, not re-verified
against a live call (same disclosure as `futures_account_reader.py`).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionFactory,
)

#: What a commission read can raise from the SDK, the network or a malformed
#: payload.
_READ_FAILURES = (
    BinanceAPIException,
    BinanceRequestException,
    RequestException,
    KeyError,
    InvalidOperation,
)


class FuturesCommissionRateReader(ICommissionRateReader):
    """Reads one Futures account's per-symbol commission rates."""

    def __init__(
        self,
        session_factory: ITradingSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider

    def commission_rate(self, symbol: str) -> CommissionRate:
        credentials = self._credentials_provider.resolve().credentials
        if credentials is None:
            raise CommissionRateUnavailableError(
                f"{symbol}: no Futures credentials configured"
            )
        try:
            client = self._session_factory.create_trading_client(credentials)
            answer: dict[str, Any] = client.futures_commission_rate(symbol=symbol)
            return CommissionRate(
                symbol=symbol,
                maker=Decimal(str(answer["makerCommissionRate"])),
                taker=Decimal(str(answer["takerCommissionRate"])),
            )
        except _READ_FAILURES as exc:
            raise CommissionRateUnavailableError(
                f"{symbol} Futures commission rate could not be read: {exc!r}"
            ) from exc
