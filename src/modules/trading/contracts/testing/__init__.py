"""The verified fakes of `trading`'s ports, and the contract suites both the
fakes and the real implementations must pass (HLD §10.3).

These are **public API**, not test scaffolding: HLD §10.3 rule 1 says a fake
ships with its contract in the provider module, and rule 4 forbids a consumer
mocking a port it does not own. A consumer's test imports the fake from here.
"""

from .contract_account_snapshot import AccountSnapshotContract
from .contract_market_metadata_provider import MarketMetadataProviderContract
from .contract_order_submission import OrderSubmissionContract
from .contract_trading_account_reader import TradingAccountReaderContract
from .contract_trading_session import TradingSessionContract
from .fake_account_snapshot import FakeAccountSnapshot
from .fake_market_metadata_provider import FakeMarketMetadataProvider
from .fake_order_submission import FakeOrderSubmission
from .fake_trading_account_reader import FakeTradingAccountReader
from .fake_trading_session import FakeTradingSession

__all__ = [
    "AccountSnapshotContract",
    "FakeAccountSnapshot",
    "FakeMarketMetadataProvider",
    "FakeOrderSubmission",
    "FakeTradingAccountReader",
    "FakeTradingSession",
    "MarketMetadataProviderContract",
    "OrderSubmissionContract",
    "TradingAccountReaderContract",
    "TradingSessionContract",
]
