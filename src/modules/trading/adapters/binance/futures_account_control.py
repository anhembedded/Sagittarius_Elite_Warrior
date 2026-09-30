"""`EPIC-028F` — `IFuturesAccountControl` for USD-M Futures.

@details `POST /fapi/v1/leverage` answers `{symbol, leverage,
maxNotionalValue}`. `POST /fapi/v1/marginType` answers `{code: 200, msg:
"success"}`, and refuses a change to the mode already in effect with
`-4046 "No need to change margin type."`; the port promises that asking for
the current mode is not an error, so `-4046` is read as success.
`open_position` reads `GET /fapi/v3/positionRisk?symbol=`, one row in One-way
mode.

Every request and the reading of its answer run inside one translation
(`_exchange_answer`), so nothing but the port's two errors leaves this class
(PR #299 review, findings 1 and 2):
- an exchange refusal becomes `AccountControlRejectedError` with Binance's
  code and message;
- a missing credential, a network failure or an answer that cannot be read
  becomes `AccountControlUnavailableError`, the cause chained. For a change,
  the message says it may have been applied, because the request was sent.

Payload shapes and error codes follow Binance's documented USD-M API; they
were not re-verified against a live call (egress to `*.binance.*` is blocked
in this sandbox), the same disclosure as `futures_account_reader.py`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
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

#: What reading an answer can raise when the payload is not the documented
#: shape.
_UNREADABLE_ANSWER = (KeyError, TypeError, ValueError, InvalidOperation)

#: What an unknown outcome means, by kind of request.
_READ_OUTCOME = "nothing was changed"
_CHANGE_OUTCOME = "it may have been applied"


@contextmanager
def _exchange_answer(what: str, outcome: str) -> Iterator[None]:
    """Translates every failure inside the block into the port's two errors:
    the exchange said no, or the outcome is unknown (`outcome` says what that
    means for this request)."""
    try:
        yield
    except BinanceAPIException as exc:
        raise AccountControlRejectedError(int(exc.code), str(exc.message)) from exc
    except (BinanceRequestException, RequestException) as exc:
        raise AccountControlUnavailableError(
            f"{what} got no answer; {outcome}: {exc}"
        ) from exc
    except _UNREADABLE_ANSWER as exc:
        raise AccountControlUnavailableError(
            f"{what} got an answer that could not be read; {outcome}: {exc!r}"
        ) from exc


class FuturesAccountControl(IFuturesAccountControl):
    """Changes one Futures account's per-symbol leverage and margin mode."""

    def __init__(
        self,
        session_factory: ITradingSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider

    def open_position(self, symbol: str) -> Decimal:
        return self._call(
            f"{symbol} position read",
            _READ_OUTCOME,
            lambda client: sum(
                (
                    Decimal(str(row["positionAmt"]))
                    for row in client.futures_position_information(symbol=symbol)
                    if row["symbol"] == symbol
                ),
                Decimal(0),
            ),
        )

    def change_leverage(self, symbol: str, leverage: int) -> LeverageSetting:
        return self._call(
            f"{symbol} leverage change to {leverage}x",
            _CHANGE_OUTCOME,
            lambda client: _leverage_setting(
                client.futures_change_leverage(symbol=symbol, leverage=leverage)
            ),
        )

    def change_margin_type(self, symbol: str, margin_type: MarginType) -> MarginType:
        try:
            self._call(
                f"{symbol} margin-mode change to {margin_type.value}",
                _CHANGE_OUTCOME,
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

    def _call[T](
        self,
        what: str,
        outcome: str,
        request: Callable[[ITradingSessionClient], T],
    ) -> T:
        credentials = self._credentials_provider.resolve().credentials
        if credentials is None:
            raise AccountControlUnavailableError(
                f"{what} not sent: no Futures credentials configured"
            )
        with _exchange_answer(what, outcome):
            return request(self._session_factory.create_trading_client(credentials))


def _leverage_setting(answer: dict[str, Any]) -> LeverageSetting:
    return LeverageSetting(
        symbol=str(answer["symbol"]),
        leverage=int(answer["leverage"]),
        max_notional=Decimal(str(answer["maxNotionalValue"])),
    )
