"""`EPIC-027H` — `ITradingAccountReader` implementation for Binance Spot:
the first read-only path this app can point at Spot Testnet, mirroring
`FuturesAccountReader`'s own shape (ping -> clock skew -> account) with
Spot's own unprefixed session-client methods and the Spot API's own
account shape (`balances: [{"asset", "free", "locked"}, ...]`, no
`assets`/`positions`).

Spot's average entry price is intentionally not computed here (ADR O6:
`GET /api/v3/myTrades`, a later phase) — this reader's result has no field
for it at all, rather than a `None` a caller might mistake for "asked and
got nothing".

**Verification note** (same disclosure as `FuturesAccountReader`'s own):
error code mapping and payload shapes are written from Binance's documented
Spot API, not re-verified against a live call — egress to every
`*.binance.*` domain is policy-blocked in this sandbox.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_spot_session_factory import (
    ISpotSessionClient,
    ISpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.TradingAdapter")

#: Binance error codes this reader can name precisely — the same
#: Binance-API-wide codes `FuturesAccountReader` classifies, duplicated
#: rather than shared: each reader stays a complete, independently
#: readable adapter (`architecture-rule.md` §5), and the table is three
#: lines.
_ERROR_CODE_TO_FAILURE_KIND: dict[int, ConnectionFailureKind] = {
    -1021: ConnectionFailureKind.CLOCK_SKEW,
    -1022: ConnectionFailureKind.BAD_SIGNATURE,
    -2015: ConnectionFailureKind.KEY_EXPIRED,
}

#: Phase 1 supports USDT-quoted pairs only (ADR D9) — the quote asset an
#: equity calculation prices every other holding against.
_QUOTE_ASSET = "USDT"

#: Anything at or below this quantity is fee-dust, not a holding worth
#: pricing — eight decimal places is Binance's own finest representable
#: unit across the symbols this app trades.
_DUST_THRESHOLD = Decimal("0.00000001")

_NETWORK_EXCEPTIONS = (BinanceAPIException, BinanceRequestException, RequestException)


def _classify_exception(exc: Exception) -> ConnectionFailureKind:
    kind = (
        _ERROR_CODE_TO_FAILURE_KIND.get(exc.code, ConnectionFailureKind.NETWORK)
        if isinstance(exc, BinanceAPIException)
        else ConnectionFailureKind.NETWORK
    )
    if kind is ConnectionFailureKind.NETWORK:
        # `BUG-137` follow-up — every other kind here already names the
        # problem (`KEY_EXPIRED`, `BAD_SIGNATURE`, ...); this catch-all
        # bucket is the one place the real exception was being discarded,
        # leaving the run log with zero evidence of what actually failed
        # (an operator staring at a bare "network" verdict with no next
        # step). Logged, never silently swallowed (`code/errors.md` #1).
        logger.error(
            "Spot Testnet connection check failed with an unclassified "
            "exception: %s: %s",
            type(exc).__name__,
            exc,
        )
    return kind


def _parse_holdings(account: dict[str, Any]) -> tuple[SpotHolding, ...]:
    holdings: list[SpotHolding] = []
    for balance in account.get("balances", []):
        try:
            free = Decimal(str(balance.get("free", "0")))
            locked = Decimal(str(balance.get("locked", "0")))
        except InvalidOperation:
            continue
        if free + locked <= 0:
            continue
        holdings.append(
            SpotHolding(
                asset=str(balance.get("asset", "")),
                free=free,
                locked=locked,
                dust_threshold=_DUST_THRESHOLD,
            )
        )
    return tuple(holdings)


class SpotAccountReader(ITradingAccountReader):
    def __init__(
        self,
        session_factory: ISpotSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        # `BUG-139` — the live UI polls `check_connection()` every few
        # seconds (`HoldingsRefreshService`); a holding with no real
        # `<asset>USDT` market (a Testnet-only junk asset, or a genuinely
        # untradeable one) fails the same ticker lookup every single poll,
        # forever. The equity-unavailable *result* is correct and
        # unchanged (`_compute_equity`'s own "never guess a partial sum"
        # discipline) — only the identical WARNING is deduplicated, so a
        # persistent, expected condition logs once instead of spamming the
        # run log every poll cycle.
        self._logged_unpriceable_assets: set[str] = set()

    def check_connection(self) -> ExchangeConnectionStatus:
        resolution = self._credentials_provider.resolve()
        if resolution.credentials is None:
            return self._status(failure=ConnectionFailureKind.NOT_CONFIGURED)

        try:
            # `Client(...)` pings on construction by default (`BUG-045`), so
            # construction must be inside this try too.
            client = self._session_factory.create_account_client(resolution.credentials)
            client.ping()
        except _NETWORK_EXCEPTIONS as exc:
            return self._status(failure=_classify_exception(exc))

        server_time_skew_ms: int | None = None
        try:
            server_time = client.get_server_time()
            server_time_skew_ms = int(time.time() * 1000) - int(
                server_time["serverTime"]
            )
        except _NETWORK_EXCEPTIONS as exc:
            return self._status(failure=_classify_exception(exc))

        try:
            account = client.get_account()
        except _NETWORK_EXCEPTIONS as exc:
            return self._status(
                failure=_classify_exception(exc),
                server_time_skew_ms=server_time_skew_ms,
            )

        holdings = _parse_holdings(account)
        quote_holding = next((h for h in holdings if h.asset == _QUOTE_ASSET), None)
        quote_balance = quote_holding.total if quote_holding is not None else Decimal(0)
        equity = self._compute_equity(client, quote_balance, holdings)

        return self._status(
            reachable=True,
            failure=None,
            server_time_skew_ms=server_time_skew_ms,
            usdt_balance=quote_balance,
            holdings=holdings,
            equity=equity,
        )

    def _compute_equity(
        self,
        client: ISpotSessionClient,
        quote_balance: Decimal,
        holdings: tuple[SpotHolding, ...],
    ) -> Decimal | None:
        """@brief Quote balance plus every non-dust holding priced against
        it. @return `None`, never a partial sum, the moment one holding
        cannot be priced — the same "never guessed" discipline this task's
        acceptance criteria apply to the average entry price."""
        equity = quote_balance
        for holding in holdings:
            if holding.asset == _QUOTE_ASSET or holding.is_dust:
                continue
            symbol = f"{holding.asset}{_QUOTE_ASSET}"
            try:
                ticker = client.get_symbol_ticker(symbol=symbol)
                price = Decimal(str(ticker["price"]))
            except (*_NETWORK_EXCEPTIONS, KeyError, InvalidOperation):
                if holding.asset not in self._logged_unpriceable_assets:
                    self._logged_unpriceable_assets.add(holding.asset)
                    logger.warning(
                        "SpotAccountReader equity: could not price %s via %s "
                        "ticker — reporting equity as unavailable rather "
                        "than a partial sum (further occurrences for this "
                        "asset are not logged again)",
                        holding.asset,
                        symbol,
                    )
                return None
            logger.info(
                "SpotAccountReader equity: priced %s via %s ticker = %s",
                holding.asset,
                symbol,
                price,
            )
            equity += holding.total * price
        return equity

    @staticmethod
    def _status(
        *,
        reachable: bool = False,
        failure: ConnectionFailureKind | None,
        server_time_skew_ms: int | None = None,
        usdt_balance: Decimal | None = None,
        holdings: tuple[SpotHolding, ...] | None = None,
        equity: Decimal | None = None,
    ) -> ExchangeConnectionStatus:
        return ExchangeConnectionStatus(
            venue=TradingVenue.SPOT_TESTNET,
            reachable=reachable,
            failure=failure,
            server_time_skew_ms=server_time_skew_ms,
            usdt_balance=usdt_balance,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
            holdings=holdings,
            equity=equity,
        )
