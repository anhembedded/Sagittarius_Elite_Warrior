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

`EPIC-028D` — the same read answers what a desk shows
(`SpotAccountSummary`): the quote asset's `free` (spendable) and `locked`
(in open orders) parts, and the equity computed below. No extra request.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.account_can_trade import (
    can_trade_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    classify_connection_failure,
    missing_key_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_parsing import (
    parse_holdings,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    SpotAccountSummary,
)
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

#: Phase 1 supports USDT-quoted pairs only (ADR D9) — the quote asset an
#: equity calculation prices every other holding against.
_QUOTE_ASSET = "USDT"

_NETWORK_EXCEPTIONS = (BinanceAPIException, BinanceRequestException, RequestException)


class SpotAccountReader(ITradingAccountReader):
    def __init__(
        self,
        session_factory: ISpotSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        venue: TradingVenue = TradingVenue.SPOT_TESTNET,
    ) -> None:
        """@param venue The Spot venue this reader reads; the factory it is
        given opens that venue's sessions (`EPIC-034` D11)."""
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._venue = venue
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
            return self._status(failure=missing_key_failure(resolution))

        try:
            # `Client(...)` pings on construction by default (`BUG-045`), so
            # construction must be inside this try too.
            client = self._session_factory.create_account_client(resolution.credentials)
            client.ping()
        except _NETWORK_EXCEPTIONS as exc:
            return self._status(failure=self._classify(exc))

        server_time_skew_ms: int | None = None
        try:
            server_time = client.get_server_time()
            server_time_skew_ms = int(time.time() * 1000) - int(
                server_time["serverTime"]
            )
        except _NETWORK_EXCEPTIONS as exc:
            return self._status(failure=self._classify(exc))

        try:
            account = client.get_account()
        except _NETWORK_EXCEPTIONS as exc:
            return self._status(
                failure=self._classify(exc),
                server_time_skew_ms=server_time_skew_ms,
            )

        holdings = parse_holdings(account)
        quote_holding = next((h for h in holdings if h.asset == _QUOTE_ASSET), None)
        quote_balance = quote_holding.total if quote_holding is not None else Decimal(0)
        equity = self._compute_equity(client, quote_balance, holdings)
        quote_free = quote_holding.free if quote_holding is not None else Decimal(0)
        summary = SpotAccountSummary(
            venue=self._venue,
            available_balance=quote_free,
            equity=equity,
            quote_asset=_QUOTE_ASSET,
            quote_free=quote_free,
            quote_locked=(
                quote_holding.locked if quote_holding is not None else Decimal(0)
            ),
        )

        return self._status(
            reachable=True,
            failure=None,
            server_time_skew_ms=server_time_skew_ms,
            usdt_balance=quote_balance,
            holdings=holdings,
            equity=equity,
            summary=summary,
            can_trade=can_trade_of(account),
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
            # DEBUG: one line per holding on every poll (`logging-rule.md` §6).
            logger.debug(
                "SpotAccountReader equity: priced %s via %s ticker = %s",
                holding.asset,
                symbol,
                price,
            )
            equity += holding.total * price
        return equity

    def _classify(self, exc: Exception) -> ConnectionFailureKind:
        return classify_connection_failure(exc, self._venue.display_name)

    def _status(
        self,
        *,
        reachable: bool = False,
        failure: ConnectionFailureKind | None,
        server_time_skew_ms: int | None = None,
        usdt_balance: Decimal | None = None,
        holdings: tuple[SpotHolding, ...] | None = None,
        equity: Decimal | None = None,
        summary: SpotAccountSummary | None = None,
        can_trade: bool | None = None,
    ) -> ExchangeConnectionStatus:
        return ExchangeConnectionStatus(
            venue=self._venue,
            reachable=reachable,
            failure=failure,
            server_time_skew_ms=server_time_skew_ms,
            usdt_balance=usdt_balance,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
            holdings=holdings,
            equity=equity,
            summary=summary,
            can_trade=can_trade,
        )
