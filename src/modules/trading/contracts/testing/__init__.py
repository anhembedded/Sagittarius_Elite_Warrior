"""The verified fakes of `trading`'s ports, and the contract suites both the
fakes and the real implementations must pass (HLD §10.3).

These are **public API**, not test scaffolding: HLD §10.3 rule 1 says a fake
ships with its contract in the provider module, and rule 4 forbids a consumer
mocking a port it does not own. A consumer's test imports the fake from here.
"""

from .fake_market_metadata_provider import FakeMarketMetadataProvider
from .fake_trading_account_reader import FakeTradingAccountReader

__all__ = ["FakeMarketMetadataProvider", "FakeTradingAccountReader"]
