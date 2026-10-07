"""`EPIC-034E` — `IVenueAccountReader` for the owner's real Spot account:
read, never traded (D4).

@details Not a `TradingVenue` and holding none of what trades: its collaborators
are a credentials resolver and `IMainnetReadSessionFactory`, whose client lists
reads only. What it reads, in this order, stopping at the first refusal:
1. the credentials (`BINANCE_MAINNET_READONLY_API_KEY` / `_SECRET`; none is
   `NOT_CONFIGURED`);
2. the key's permissions (`apiRestrictions`): a key that can withdraw is refused
   with `WITHDRAWAL_ENABLED` *before any account data is read* (D5); a key that
   can trade is accepted, and the snapshot says so for the screen to advise;
3. the account (balances, commission rates, `canTrade`), the open orders, the
   symbol's filters and its price.

Unlike the testnet venues it reads the symbol's filters and price from the
public mainnet endpoints too, so a snapshot has the same shape on every source.

Verification note: see `mainnet_read_session_factory.py`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from binance.exceptions import BinanceAPIException, BinanceRequestException
from requests.exceptions import RequestException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.account_can_trade import (
    can_trade_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.connection_failure import (
    classify_connection_failure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.key_permissions_parser import (
    parse_key_permissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.market_price_reads import (
    parse_book_ticker,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_account_parsing import (
    parse_account_commission,
    parse_holdings,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_parser import (
    parse_spot_exchange_info,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_account_reader import (
    IVenueAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_permissions import (
    KeyPermissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_account_snapshot import (
    QUOTE_ASSET,
    VenueAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_credentials_resolver import (
    ICredentialsResolver,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_mainnet_read_client import (
    IMainnetReadClient,
    IMainnetReadSessionFactory,
)

logger = logging.getLogger("App.MainnetReadOnly")

_SOURCE = AccountSource.SPOT_MAINNET_READONLY
_THE_KEY = "the key's permissions"
_NETWORK_FAILURES = (BinanceAPIException, BinanceRequestException, RequestException)
_PARSE_FAILURES = (KeyError, TypeError, ValueError, InvalidOperation)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MainnetReadOnlyAccountReader(IVenueAccountReader):
    def __init__(
        self,
        credentials: ICredentialsResolver,
        clients: IMainnetReadSessionFactory,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._credentials = credentials
        self._clients = clients
        self._clock = clock

    @property
    def source(self) -> AccountSource:
        return _SOURCE

    def read(self, symbol: str) -> VenueAccountSnapshot | ConnectFailure:
        resolved = self._credentials.resolve().credentials
        if resolved is None:
            return ConnectFailure(_SOURCE, ConnectionFailureKind.NOT_CONFIGURED)
        try:
            client = self._clients.create_read_client(resolved)
            permissions = parse_key_permissions(client.get_account_api_permissions())
        except _NETWORK_FAILURES as exc:
            return self._failed(exc, _THE_KEY)
        except _PARSE_FAILURES as exc:
            return self._unreadable(_THE_KEY, exc)
        if permissions.can_withdraw:
            logger.warning(
                "Mainnet read-only: the key can withdraw; refused before reading "
                "anything [mainnet-readonly]"
            )
            return ConnectFailure(
                _SOURCE, ConnectionFailureKind.WITHDRAWAL_ENABLED, "withdrawals"
            )
        return self._snapshot(client, symbol, permissions)

    def _snapshot(
        self, client: IMainnetReadClient, symbol: str, permissions: KeyPermissions
    ) -> VenueAccountSnapshot | ConnectFailure:
        try:
            account = client.get_account()
            open_orders = client.get_open_orders()
            exchange_info = client.get_exchange_info()
            book = parse_book_ticker(client.get_orderbook_ticker(symbol=symbol), symbol)
            commission = parse_account_commission(account, symbol)
            holdings = parse_holdings(account)
            rules = next(
                (
                    m
                    for m in parse_spot_exchange_info(exchange_info)
                    if m.symbol == symbol
                ),
                None,
            )
            available = self._available(holdings)
        except _NETWORK_FAILURES as exc:
            return self._failed(exc, "the account")
        except _PARSE_FAILURES as exc:
            return self._unreadable("the account", exc)
        if rules is None:
            return ConnectFailure(
                _SOURCE,
                ConnectionFailureKind.NETWORK,
                f"the filters: {symbol} is not listed",
            )
        if not (book.has_ask or book.has_bid):
            return ConnectFailure(
                _SOURCE,
                ConnectionFailureKind.NETWORK,
                f"the price: {symbol} has no orders",
            )
        return VenueAccountSnapshot(
            source=_SOURCE,
            symbol=symbol,
            read_at=self._clock(),
            quote_asset=QUOTE_ASSET,
            available=available,
            holdings=tuple(h for h in holdings if not h.is_dust),
            commission=commission,
            can_trade=can_trade_of(account),
            rules=rules,
            price=book.ask_price if book.has_ask else book.bid_price,
            key_permissions=permissions,
            open_order_count=len(open_orders),
        )

    @staticmethod
    def _available(holdings: tuple[SpotHolding, ...]) -> Decimal:
        return next((h.free for h in holdings if h.asset == QUOTE_ASSET), Decimal(0))

    def _failed(self, exc: Exception, what: str) -> ConnectFailure:
        kind = classify_connection_failure(exc, "Mainnet read-only")
        # A named kind says it all; only the catch-all names the read.
        return ConnectFailure(
            _SOURCE, kind, what if kind is ConnectionFailureKind.NETWORK else ""
        )

    def _unreadable(self, what: str, cause: Exception) -> ConnectFailure:
        logger.warning(
            "Mainnet read-only: %s could not be read: %r [mainnet-readonly]",
            what,
            cause,
        )
        return ConnectFailure(_SOURCE, ConnectionFailureKind.NETWORK, what)
