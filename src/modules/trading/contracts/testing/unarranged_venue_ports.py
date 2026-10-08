"""`EPIC-028B` — stand-ins for the per-venue ports a test did not arrange.

@details A `VenueContext` holds every port of one venue, but a consumer test
outside `trading` touches one or two of them: `trade-once` reads a venue's
metadata and balance, never its user-data stream. Each class here fails the
test, naming the port, the moment anything calls it. That is the opposite of
a `Mock`, which would answer and let the test pass for the wrong reason
(`testing-rule.md` §2), and the reason none of them has a contract suite:
they promise nothing except that they are never reached.

`fake_venue_context()` puts one in every slot the test leaves empty.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import NoReturn

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.active_symbol import (
    ActiveSymbol,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.best_bid_ask import (
    BestBidAsk,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.commission_rate import (
    CommissionRate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.history_gaps import (
    HistoryGaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_book_ticker_reader import (
    IBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_commission_rate_reader import (
    ICommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_account_control import (
    IFuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_mark_price_reader import (
    IMarkPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_symbol_order_metadata_cache import (
    ISymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.mark_price import (
    MarkPrice,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)


def _not_arranged(port: str) -> NoReturn:
    raise AssertionError(
        f"{port} was not arranged for this test; pass one to fake_venue_context()."
    )


class UnarrangedCredentialsProvider(IExchangeCredentialsProvider):
    def resolve(self) -> ResolvedCredentials:
        _not_arranged("IExchangeCredentialsProvider")

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        _not_arranged("IExchangeCredentialsProvider")

    def remove_stored(self) -> None:
        _not_arranged("IExchangeCredentialsProvider")


class UnarrangedMetadataCache(ISymbolOrderMetadataCache):
    def get(self, symbol: str) -> SymbolOrderMetadata | None:
        _not_arranged("ISymbolOrderMetadataCache")

    def put(self, metadata: SymbolOrderMetadata) -> None:
        _not_arranged("ISymbolOrderMetadataCache")

    def has(self, symbol: str) -> bool:
        _not_arranged("ISymbolOrderMetadataCache")

    def clear(self) -> None:
        _not_arranged("ISymbolOrderMetadataCache")


class UnarrangedClientFactory(ITradingClientFactory):
    def accepted_order_types(self) -> frozenset[OrderType]:
        _not_arranged("ITradingClientFactory")

    def create(self, mode: OrderSubmissionMode) -> ITradingClient:
        _not_arranged("ITradingClientFactory")


class UnarrangedUserDataStream(IUserDataStream):
    @property
    def is_running(self) -> bool:
        _not_arranged("IUserDataStream")

    def start(self) -> bool:
        _not_arranged("IUserDataStream")

    def stop(self) -> bool:
        _not_arranged("IUserDataStream")


class UnarrangedHistoryReader(IAccountHistoryReader):
    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        _not_arranged("IAccountHistoryReader")

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        _not_arranged("IAccountHistoryReader")

    def active_symbols(self, since: datetime) -> tuple[ActiveSymbol, ...]:
        _not_arranged("IAccountHistoryReader")

    def every_symbol_scan_limit(self) -> int | None:
        _not_arranged("IAccountHistoryReader")

    def known_gaps(self) -> HistoryGaps:
        _not_arranged("IAccountHistoryReader")


class UnarrangedCommissionRateReader(ICommissionRateReader):
    def commission_rate(self, symbol: str) -> CommissionRate:
        _not_arranged("ICommissionRateReader")


class UnarrangedAccountControl(IFuturesAccountControl):
    def open_position(self, symbol: str) -> Decimal:
        _not_arranged("IFuturesAccountControl")

    def symbol_setting(self, symbol: str) -> FuturesSymbolSetting:
        _not_arranged("IFuturesAccountControl")

    def leverage_brackets(self, symbol: str) -> LeverageBrackets:
        _not_arranged("IFuturesAccountControl")

    def change_leverage(self, symbol: str, leverage: int) -> LeverageSetting:
        _not_arranged("IFuturesAccountControl")

    def change_margin_type(self, symbol: str, margin_type: MarginType) -> MarginType:
        _not_arranged("IFuturesAccountControl")


class UnarrangedBookTickerReader(IBookTickerReader):
    def best_bid_ask(self, symbol: str) -> BestBidAsk:
        _not_arranged("IBookTickerReader")


class UnarrangedMarkPriceReader(IMarkPriceReader):
    def mark_price(self, symbol: str) -> MarkPrice:
        _not_arranged("IMarkPriceReader")
