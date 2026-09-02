"""`EPIC-021D` — `ITradingAccountReader` implementation: the first code
path in this app allowed to sign a request to Binance Futures Testnet.

@details Four read-only calls, not the task's originally-planned three
(`futures_ping` -> `futures_time` -> `futures_account` -> **`futures_get_
position_mode`**): position mode is not part of `futures_account()`'s
payload — it is its own signed endpoint
(`GET /fapi/v1/positionSide/dual`). Getting this wrong would mean silently
reporting every account as One-way, exactly the "assumption fails quietly"
`EPIC-021D` §2.3 exists to prevent — so the extra call is made rather than
guessed away.

**Verification note** (same disclosure as `EPIC-021A`/`EPIC-021C`): error
code mapping (`-1021`/`-1022`/`-2015`) and the account/position-mode
payload shapes are written from Binance's documented futures API, not
re-verified against a live call — egress to every `*.binance.*` domain is
policy-blocked in this sandbox. Unrecognized error codes degrade to
`ConnectionFailureKind.NETWORK` rather than crashing or guessing a more
specific kind.
"""

from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)

#: Binance error codes this reader can name precisely. Any other
#: `BinanceAPIException` code -- or a network-level failure with no code at
#: all -- degrades to `ConnectionFailureKind.NETWORK`.
_ERROR_CODE_TO_FAILURE_KIND: dict[int, ConnectionFailureKind] = {
    -1021: ConnectionFailureKind.CLOCK_SKEW,
    -1022: ConnectionFailureKind.BAD_SIGNATURE,
    -2015: ConnectionFailureKind.KEY_EXPIRED,
}

_USDT_ASSET = "USDT"


def _classify_exception(exc: Exception) -> ConnectionFailureKind:
    if isinstance(exc, BinanceAPIException):
        return _ERROR_CODE_TO_FAILURE_KIND.get(exc.code, ConnectionFailureKind.NETWORK)
    return ConnectionFailureKind.NETWORK


def _extract_usdt_balance(account: dict[str, Any]) -> Decimal | None:
    for asset in account.get("assets", []):
        if asset.get("asset") == _USDT_ASSET:
            try:
                return Decimal(str(asset.get("walletBalance")))
            except (InvalidOperation, TypeError):
                return None
    return None


def _open_positions(account: dict[str, Any]) -> list[dict[str, Any]]:
    open_positions = []
    for position in account.get("positions", []):
        try:
            amount = Decimal(str(position.get("positionAmt", "0")))
        except (InvalidOperation, TypeError):
            continue
        if amount != 0:
            open_positions.append(position)
    return open_positions


def _infer_margin_type(open_positions: list[dict[str, Any]]) -> MarginType | None:
    """Margin type is per-symbol on Binance Futures, not account-wide —
    there is no meaningful "account default" to report when nothing is
    open yet. Reports the first open position's margin type as a
    representative sample, matching what `ExchangeConnectionStatus`'s own
    docstring promises."""
    if not open_positions:
        return None
    is_isolated = bool(open_positions[0].get("isolated", False))
    return MarginType.ISOLATED if is_isolated else MarginType.CROSSED


class FuturesAccountReader(ITradingAccountReader):
    def __init__(
        self,
        session_factory: ExchangeSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider

    def check_connection(self) -> ExchangeConnectionStatus:
        resolution = self._credentials_provider.resolve()
        if resolution.credentials is None:
            # `venue` still reports FUTURES_TESTNET rather than DISABLED:
            # this diagnostic only ever checks the one futures venue that
            # exists (ADR §3), and `NOT_CONFIGURED` already says the real
            # story on its own — a second, differently-named "no venue"
            # signal here would only be confusing.
            return self._status(failure=ConnectionFailureKind.NOT_CONFIGURED)

        try:
            # `Client(...)`'s own constructor pings on construction by
            # default (`ping=True`, same trigger as `BUG-045`) — a network
            # failure can surface right here, before any of this reader's
            # own calls run, so construction must be inside this try too.
            client = self._session_factory.create_trading_client(resolution.credentials)
            client.futures_ping()
        except (BinanceAPIException, BinanceRequestException, RequestException) as exc:
            return self._status(failure=_classify_exception(exc))

        server_time_skew_ms: int | None = None
        try:
            server_time = client.futures_time()
            server_time_skew_ms = int(time.time() * 1000) - int(
                server_time["serverTime"]
            )
        except (BinanceAPIException, BinanceRequestException, RequestException) as exc:
            return self._status(failure=_classify_exception(exc))

        try:
            account = client.futures_account()
        except (BinanceAPIException, BinanceRequestException, RequestException) as exc:
            return self._status(
                failure=_classify_exception(exc),
                server_time_skew_ms=server_time_skew_ms,
            )

        usdt_balance = _extract_usdt_balance(account)
        open_positions = _open_positions(account)
        margin_type = _infer_margin_type(open_positions)

        try:
            position_mode_payload = client.futures_get_position_mode()
        except (BinanceAPIException, BinanceRequestException, RequestException) as exc:
            return self._status(
                failure=_classify_exception(exc),
                server_time_skew_ms=server_time_skew_ms,
                usdt_balance=usdt_balance,
                margin_type=margin_type,
                open_position_count=len(open_positions),
            )
        position_mode = (
            PositionMode.HEDGE
            if position_mode_payload.get("dualSidePosition")
            else PositionMode.ONE_WAY
        )

        failure = (
            ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED
            if position_mode is PositionMode.HEDGE
            else None
        )
        return self._status(
            reachable=True,
            failure=failure,
            server_time_skew_ms=server_time_skew_ms,
            usdt_balance=usdt_balance,
            position_mode=position_mode,
            margin_type=margin_type,
            open_position_count=len(open_positions),
        )

    @staticmethod
    def _status(
        *,
        reachable: bool = False,
        failure: ConnectionFailureKind | None,
        server_time_skew_ms: int | None = None,
        usdt_balance: Decimal | None = None,
        position_mode: PositionMode | None = None,
        margin_type: MarginType | None = None,
        open_position_count: int | None = None,
    ) -> ExchangeConnectionStatus:
        return ExchangeConnectionStatus(
            venue=TradingVenue.FUTURES_TESTNET,
            reachable=reachable,
            failure=failure,
            server_time_skew_ms=server_time_skew_ms,
            usdt_balance=usdt_balance,
            position_mode=position_mode,
            margin_type=margin_type,
            open_position_count=open_position_count,
        )
