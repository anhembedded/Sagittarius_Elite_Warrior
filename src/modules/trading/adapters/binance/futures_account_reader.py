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

`EPIC-028D` — the same `futures_account()` payload also answers what a desk
shows (`FuturesAccountSummary`): the USDT asset's `availableBalance`,
`walletBalance`, `marginBalance` and `unrealizedProfit`.

`EPIC-028O` — which figures count depends on the account's Multi-Assets mode
(`GET /fapi/v1/multiAssetsMargin`). The mode changes only when the user
changes it, so it is read at most once per `ASSET_MODE_TTL_SECONDS`, not on
every check: the summary refresh runs a check every 5 s (as often as every
second, `module.py`), and at weight 30 per read (Binance's published USD-M
table) reading it per check would add 360 to 1 800 weight a minute against
Binance's 2 400 a minute IP budget (the PR #304 review, finding 1). Once per
five minutes costs 6 a minute; a change of mode shows within five minutes. In
Multi-Assets mode the summary reads the account-wide `totalWalletBalance`,
`totalMarginBalance`, `totalUnrealizedProfit` and `availableBalance` (USD,
every margin asset) and says so in `asset_mode`. A mode that cannot be read
leaves the summary `None`, like an unreadable figure: guessing the mode would
label one figure as the other.

**Verification note** (same disclosure as `EPIC-021A`/`EPIC-021C`): error
code mapping (`connection_failure.py`: `-1021`/`-1022`/`-2015`) and the account/position-mode
payload shapes are written from Binance's documented futures API, not
re-verified against a live call — egress to every `*.binance.*` domain is
policy-blocked in this sandbox. Unrecognized error codes degrade to
`ConnectionFailureKind.NETWORK` rather than crashing or guessing a more
specific kind.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.account_can_trade import (
    can_trade_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    classify_connection_failure,
    missing_key_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AssetMode,
    FuturesAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    MarginType,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionClient,
    ITradingSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_USDT_ASSET = "USDT"

#: How long a read Multi-Assets mode is trusted before it is read again.
ASSET_MODE_TTL_SECONDS = 300.0

#: What reading the Multi-Assets mode can raise: the SDK, the network, or an
#: answer of another shape.
_SUMMARY_READ_FAILURES = (
    BinanceAPIException,
    BinanceRequestException,
    RequestException,
    KeyError,
    TypeError,
)

logger = logging.getLogger("App.TradingAdapter")


def _extract_usdt_balance(account: dict[str, Any]) -> Decimal | None:
    for asset in account.get("assets", []):
        if asset.get("asset") == _USDT_ASSET:
            try:
                return Decimal(str(asset.get("walletBalance")))
            except (InvalidOperation, TypeError):
                return None
    return None


def _usdt_asset(account: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (a for a in account.get("assets", []) if a.get("asset") == _USDT_ASSET), None
    )


#: The summary's four figures, by mode: `(available, wallet, margin,
#: unrealized)` keys in the asset row (Single-Asset) or the account
#: (Multi-Assets).
_SUMMARY_KEYS = {
    AssetMode.SINGLE_ASSET: (
        "availableBalance",
        "walletBalance",
        "marginBalance",
        "unrealizedProfit",
    ),
    AssetMode.MULTI_ASSETS: (
        "availableBalance",
        "totalWalletBalance",
        "totalMarginBalance",
        "totalUnrealizedProfit",
    ),
}


def _asset_mode(answer: dict[str, Any]) -> AssetMode:
    """@throws KeyError, TypeError The answer is not
    `{"multiAssetsMargin": <bool>}`."""
    multi = answer["multiAssetsMargin"]
    if not isinstance(multi, bool):
        raise TypeError(f"multiAssetsMargin is not a boolean: {multi!r}")
    return AssetMode.MULTI_ASSETS if multi else AssetMode.SINGLE_ASSET


def _parse_summary(
    figures: dict[str, Any],
    position_mode: PositionMode,
    asset_mode: AssetMode,
    venue: TradingVenue,
) -> FuturesAccountSummary:
    """The desk's figures from `figures`: the USDT asset row in Single-Asset
    mode, the account itself in Multi-Assets mode. @throws KeyError,
    InvalidOperation or TypeError when a figure is missing or not a
    number."""
    available, wallet, margin, unrealized = (
        Decimal(str(figures[key])) for key in _SUMMARY_KEYS[asset_mode]
    )
    return FuturesAccountSummary(
        venue=venue,
        available_balance=available,
        equity=margin,
        wallet_balance=wallet,
        margin_balance=margin,
        unrealized_pnl=unrealized,
        position_mode=position_mode,
        asset_mode=asset_mode,
    )


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
        session_factory: ITradingSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        clock: Callable[[], float] = time.monotonic,
        venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
    ) -> None:
        """@param venue The Futures venue this reader reads; the factory it is
        given opens that venue's sessions (`EPIC-034` D11)."""
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._venue = venue
        self._clock = clock
        #: `EPIC-028O` — the last mode read and when; a failed read is never
        #: cached.
        self._asset_mode_read: tuple[AssetMode, float] | None = None
        #: `EPIC-028D` — whether the current run of unreadable summaries has
        #: been reported. The account is read every few seconds; a USDT
        #: asset that lacks a figure for good is one WARNING, not one per
        #: tick, and a readable summary re-arms it (the PR #296 review, Q4).
        self._summary_failure_reported = False

    def check_connection(self) -> ExchangeConnectionStatus:
        resolution = self._credentials_provider.resolve()
        if resolution.credentials is None:
            # `venue` still names this reader's own venue rather than
            # DISABLED: `NOT_CONFIGURED` already says the real story on its
            # own — a second, differently-named "no venue" signal here would
            # only be confusing.
            return self._status(failure=missing_key_failure(resolution))

        try:
            # `Client(...)`'s own constructor pings on construction by
            # default (`ping=True`, same trigger as `BUG-045`) — a network
            # failure can surface right here, before any of this reader's
            # own calls run, so construction must be inside this try too.
            client = self._session_factory.create_trading_client(resolution.credentials)
            client.futures_ping()
        except (BinanceAPIException, BinanceRequestException, RequestException) as exc:
            return self._status(failure=self._classify(exc))

        server_time_skew_ms: int | None = None
        try:
            server_time = client.futures_time()
            server_time_skew_ms = int(time.time() * 1000) - int(
                server_time["serverTime"]
            )
        except (BinanceAPIException, BinanceRequestException, RequestException) as exc:
            return self._status(failure=self._classify(exc))

        try:
            account = client.futures_account()
        except (BinanceAPIException, BinanceRequestException, RequestException) as exc:
            return self._status(
                failure=self._classify(exc),
                server_time_skew_ms=server_time_skew_ms,
            )

        usdt_balance = _extract_usdt_balance(account)
        open_positions = _open_positions(account)
        margin_type = _infer_margin_type(open_positions)

        try:
            position_mode_payload = client.futures_get_position_mode()
        except (BinanceAPIException, BinanceRequestException, RequestException) as exc:
            return self._status(
                failure=self._classify(exc),
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
            summary=self._read_summary(client, account, position_mode),
            can_trade=can_trade_of(account),
        )

    def _read_summary(
        self,
        client: ITradingSessionClient,
        account: dict[str, Any],
        position_mode: PositionMode,
    ) -> FuturesAccountSummary | None:
        """`None` when the account's mode or one of its figures cannot be
        read, or a Single-Asset account has no USDT asset, rather than a
        summary with an invented zero or the wrong mode's figures."""
        try:
            asset_mode = self._asset_mode(client)
        except _SUMMARY_READ_FAILURES as exc:
            self._report_unreadable_summary("its Multi-Assets mode", exc)
            return None
        figures = (
            account if asset_mode is AssetMode.MULTI_ASSETS else _usdt_asset(account)
        )
        if figures is None:
            return None
        try:
            summary = _parse_summary(figures, position_mode, asset_mode, self._venue)
        except (KeyError, InvalidOperation, TypeError) as exc:
            self._report_unreadable_summary(
                f"a balance figure ({asset_mode.value})", exc
            )
            return None
        if self._summary_failure_reported:
            self._summary_failure_reported = False
            logger.info("Futures account summary readable again")
        return summary

    def _asset_mode(self, client: ITradingSessionClient) -> AssetMode:
        """The mode read at most `ASSET_MODE_TTL_SECONDS` ago, or read now."""
        now = self._clock()
        cached = self._asset_mode_read
        if cached is not None and 0 <= now - cached[1] < ASSET_MODE_TTL_SECONDS:
            return cached[0]
        mode = _asset_mode(client.futures_get_multi_assets_mode())
        self._asset_mode_read = (mode, now)
        logger.debug("[account-summary] Futures asset mode read: %s", mode.value)
        return mode

    def _report_unreadable_summary(self, what: str, cause: Exception) -> None:
        if not self._summary_failure_reported:
            self._summary_failure_reported = True
            logger.warning(
                "Futures account summary could not read %s — no account "
                "summary until it is readable again (not logged again until "
                "then): %r",
                what,
                cause,
            )
        else:
            logger.debug("Futures account summary still unreadable: %r", cause)

    def _classify(self, exc: Exception) -> ConnectionFailureKind:
        return classify_connection_failure(exc, self._venue.display_name)

    def _status(
        self,
        *,
        reachable: bool = False,
        failure: ConnectionFailureKind | None,
        server_time_skew_ms: int | None = None,
        usdt_balance: Decimal | None = None,
        position_mode: PositionMode | None = None,
        margin_type: MarginType | None = None,
        open_position_count: int | None = None,
        summary: FuturesAccountSummary | None = None,
        can_trade: bool | None = None,
    ) -> ExchangeConnectionStatus:
        return ExchangeConnectionStatus(
            venue=self._venue,
            reachable=reachable,
            failure=failure,
            server_time_skew_ms=server_time_skew_ms,
            usdt_balance=usdt_balance,
            position_mode=position_mode,
            margin_type=margin_type,
            open_position_count=open_position_count,
            summary=summary,
            can_trade=can_trade,
        )
