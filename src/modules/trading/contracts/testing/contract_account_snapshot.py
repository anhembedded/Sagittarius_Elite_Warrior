"""The contract suite for `IAccountSnapshot` (HLD §10.3).

Four guarantees:

1. the connection answer is the state the venue is in — the fields Settings,
   the CLI `exchange-status` command and `submit()`'s first gate read;
2. it **never raises**: every failure is a named value inside the answer, and
   `submit()`'s gate has no `try` around it;
3. an unreachable venue still answers, and names why — `reachable=False` with
   `failure=None` tells a user nothing and no UI branches on it;
4. `open_positions()` answers a tuple, empty when nothing is open, because a
   caller rendering a table already handles empty and would crash on `None`.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_snapshot import (
    IAccountSnapshot,
)

#: How a subclass puts a connection state where its implementation reports it.
type GivenAccount = Callable[[ExchangeConnectionStatus], None]


class AccountSnapshotContract:
    """Inherit this, provide `impl` and `given_account`. Both must pass it."""

    @pytest.fixture
    def impl(self) -> IAccountSnapshot:
        raise NotImplementedError(
            "an AccountSnapshotContract subclass must provide an `impl` fixture"
        )

    @pytest.fixture
    def given_account(self) -> GivenAccount:
        raise NotImplementedError(
            "an AccountSnapshotContract subclass must provide a `given_account` "
            "fixture that puts a status where its implementation reports it"
        )

    def test_the_answer_is_the_state_the_venue_is_in(
        self,
        impl: IAccountSnapshot,
        given_account: GivenAccount,
        ready_status: ExchangeConnectionStatus,
    ) -> None:
        given_account(ready_status)

        answer = impl.check_connection()

        assert answer.reachable is True
        assert answer.failure is None
        assert answer.usdt_balance == ready_status.usdt_balance

    def test_it_never_raises(
        self,
        impl: IAccountSnapshot,
        given_account: GivenAccount,
        unreachable_status: ExchangeConnectionStatus,
    ) -> None:
        given_account(unreachable_status)

        assert impl.check_connection() is not None

    def test_an_unreachable_venue_names_why(
        self,
        impl: IAccountSnapshot,
        given_account: GivenAccount,
        unreachable_status: ExchangeConnectionStatus,
    ) -> None:
        given_account(unreachable_status)

        answer = impl.check_connection()

        assert answer.reachable is False
        assert answer.failure is not None

    def test_open_positions_is_a_tuple_and_empty_means_empty(
        self,
        impl: IAccountSnapshot,
        given_account: GivenAccount,
        ready_status: ExchangeConnectionStatus,
    ) -> None:
        given_account(ready_status)

        answer = impl.open_positions()

        assert isinstance(answer, tuple)
        assert answer == ()
