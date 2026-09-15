"""`FakeTradingAccountReader` — `ITradingAccountReader`'s verified fake.

@par Why a fake and not a `Mock`
Same reason as the provider next door (`EPIC-025` PR 1.3a, HLD §10.3 rule 4),
and one more that is specific to this port: its docstring promises that
`check_connection()` **never raises** — every failure is a named value inside
the answer. A `Mock` can be configured to raise and still satisfy
`Mock(spec=ITradingAccountReader)`, so the substitution can quietly break the
one guarantee every caller was written against. This fake cannot raise, and
`TradingAccountReaderContract` is what says so for both implementations.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: What the fake answers when a test has not said otherwise: unreachable, for
#: the reason a developer with no keys actually hits (NOT_CONFIGURED: no
#: credentials configured, so no network call was even attempted). A fake whose default is
#: "everything is fine" makes a test that forgot to seed pass for the wrong
#: reason.
_UNCONFIGURED = ExchangeConnectionStatus(
    venue=TradingVenue.DISABLED,
    reachable=False,
    failure=ConnectionFailureKind.NOT_CONFIGURED,
    server_time_skew_ms=None,
    usdt_balance=None,
    position_mode=None,
    margin_type=None,
    open_position_count=None,
)


class FakeTradingAccountReader(ITradingAccountReader):
    """The connection state a test says the venue is in."""

    def __init__(self, status: ExchangeConnectionStatus = _UNCONFIGURED) -> None:
        self._status = status
        #: How many times the account was checked — the connection check is a
        #: network round trip on the real implementation, so a caller doing it
        #: per candle is a defect a test should be able to see.
        self.checks = 0

    def answer_with(self, status: ExchangeConnectionStatus) -> None:
        """Sets what the next check reports."""
        self._status = status

    def check_connection(self) -> ExchangeConnectionStatus:
        self.checks += 1
        return self._status
