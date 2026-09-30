"""`EPIC-028F` — `IFuturesAccountControl` for USD-M Futures.

@details `POST /fapi/v1/leverage` answers `{symbol, leverage,
maxNotionalValue}`. `POST /fapi/v1/marginType` answers `{code: 200, msg:
"success"}`, and refuses a change to the mode already in effect with
`-4046 "No need to change margin type."`; the port promises that asking for
the current mode is not an error, so `-4046` is read as success. Every other
exchange refusal becomes `AccountControlRejectedError` with Binance's code
and message; a missing credential or a network failure becomes
`AccountControlUnavailableError`, the cause chained.

Payload shapes and error codes follow Binance's documented USD-M API; they
were not re-verified against a live call (egress to `*.binance.*` is blocked
in this sandbox), the same disclosure as `futures_account_reader.py`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_rejected_error import (
    AccountControlRejectedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_unavailable_error import (
    AccountControlUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_account_control import (
    IFuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
    ITradingSessionFactory,
)

logger = logging.getLogger("App.FuturesAccountControl")

#: Binance's answer to a margin-mode change to the mode already in effect.
NO_NEED_TO_CHANGE_MARGIN_TYPE = -4046


@contextmanager
def _exchange_answer(what: str) -> Iterator[None]:
    """Translates the SDK's failures inside the block into the port's two
    errors: the exchange said no, or the exchange never answered."""
    try:
        yield
    except BinanceAPIException as exc:
        raise AccountControlRejectedError(int(exc.code), str(exc.message)) from exc
    except (BinanceRequestException, RequestException) as exc:
        raise AccountControlUnavailableError(f"{what}: {exc}") from exc


class FuturesAccountControl(IFuturesAccountControl):
    """Changes one Futures account's per-symbol leverage and margin mode."""

    def __init__(
        self,
        session_factory: ITradingSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider

    def change_leverage(self, symbol: str, leverage: int) -> LeverageSetting:
        answer = self._call(
            f"{symbol} leverage could not be changed",
            lambda client: client.futures_change_leverage(
                symbol=symbol, leverage=leverage
            ),
        )
        return LeverageSetting(
            symbol=str(answer["symbol"]),
            leverage=int(answer["leverage"]),
            max_notional=Decimal(str(answer["maxNotionalValue"])),
        )

    def change_margin_type(self, symbol: str, margin_type: MarginType) -> MarginType:
        try:
            self._call(
                f"{symbol} margin mode could not be changed",
                lambda client: client.futures_change_margin_type(
                    symbol=symbol, marginType=margin_type.value.upper()
                ),
            )
        except AccountControlRejectedError as refusal:
            if refusal.code != NO_NEED_TO_CHANGE_MARGIN_TYPE:
                raise
            logger.info(
                "[account-control] %s is already %s; nothing changed",
                symbol,
                margin_type.value,
            )
        return margin_type

    def _call(
        self, what: str, request: Callable[[ITradingSessionClient], dict[str, Any]]
    ) -> dict[str, Any]:
        credentials = self._credentials_provider.resolve().credentials
        if credentials is None:
            raise AccountControlUnavailableError(
                f"{what}: no Futures credentials configured"
            )
        with _exchange_answer(what):
            return request(self._session_factory.create_trading_client(credentials))
