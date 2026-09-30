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
from typing import NoReturn

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
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
    def create(self, mode: OrderSubmissionMode) -> ITradingClient:
        _not_arranged("ITradingClientFactory")


class UnarrangedUserDataStream(IUserDataStream):
    def start(self) -> bool:
        _not_arranged("IUserDataStream")

    def stop(self) -> bool:
        _not_arranged("IUserDataStream")


class UnarrangedHistoryReader(IAccountHistoryReader):
    def order_history(self, symbol: str, since: datetime) -> tuple[OrderRecord, ...]:
        _not_arranged("IAccountHistoryReader")

    def trade_history(self, symbol: str, since: datetime) -> tuple[TradeRecord, ...]:
        _not_arranged("IAccountHistoryReader")

    def active_symbols(self) -> tuple[str, ...]:
        _not_arranged("IAccountHistoryReader")
