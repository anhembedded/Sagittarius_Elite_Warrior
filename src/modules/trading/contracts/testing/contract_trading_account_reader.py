"""The contract suite for `ITradingAccountReader` (HLD §10.3).

Three guarantees, all of them things a measured consumer depends on
(HLD §10.3 rule 2):

1. the answer is the state the venue is in — the fields the Settings screen,
   the CLI `exchange-status` command and `execute_order`'s safety gate read;
2. **it never raises.** The port's docstring states this and every caller is
   written against it: `execute_order`'s `_first_blocked_safety_gate()` reads
   `status.reachable` and `status.failure` with no `try`, so an
   implementation that raised would take down the order path rather than
   block one order. It is exactly the promise a `Mock(spec=...)` can be
   configured to break while still satisfying the spec;
3. an unreachable venue still answers, with the reason named — "why did it
   stop" is what the user is shown, so `reachable=False` with
   `failure=None` is not a valid answer.

**One hook.** A subclass supplies `given_status`, because the fake is told
directly and the real `FuturesAccountReader` is told by the venue.

The real implementation's half of this suite runs against the fake exchange
server in `tests/integration/`, and arrives with `EPIC-025` PR 1.3b: today
`FuturesAccountReader` takes the `ExchangeSessionFactory` instance shared with
`market_data`, which is the object 1.3b splits one-per-context.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)

#: How a subclass puts a connection state where its implementation reports it.
type GivenStatus = Callable[[ExchangeConnectionStatus], None]


class TradingAccountReaderContract:
    """Inherit this, provide `impl` and `given_status`. Both must pass it."""

    @pytest.fixture
    def impl(self) -> ITradingAccountReader:
        raise NotImplementedError(
            "a TradingAccountReaderContract subclass must provide an `impl` "
            "fixture returning the ITradingAccountReader under test"
        )

    @pytest.fixture
    def given_status(self) -> GivenStatus:
        raise NotImplementedError(
            "a TradingAccountReaderContract subclass must provide a "
            "`given_status` fixture that puts a status where its "
            "implementation reports it"
        )

    def test_the_answer_is_the_state_the_venue_is_in(
        self,
        impl: ITradingAccountReader,
        given_status: GivenStatus,
        ready_status: ExchangeConnectionStatus,
    ) -> None:
        given_status(ready_status)

        answer = impl.check_connection()

        assert answer.reachable is True
        assert answer.failure is None
        assert answer.usdt_balance == ready_status.usdt_balance
        assert answer.venue is ready_status.venue

    def test_it_never_raises(
        self,
        impl: ITradingAccountReader,
        given_status: GivenStatus,
        unreachable_status: ExchangeConnectionStatus,
    ) -> None:
        """`execute_order`'s safety gate reads this with no `try` — an
        implementation that raised would stop the order path instead of
        blocking one order."""
        given_status(unreachable_status)

        assert impl.check_connection() is not None

    def test_an_unreachable_venue_names_why(
        self,
        impl: ITradingAccountReader,
        given_status: GivenStatus,
        unreachable_status: ExchangeConnectionStatus,
    ) -> None:
        """`reachable=False` with `failure=None` tells the user nothing, and
        the UI has no branch for it."""
        given_status(unreachable_status)

        answer = impl.check_connection()

        assert answer.reachable is False
        assert answer.failure is not None
