"""The contract suite for `IMarketDataSync` (HLD §10.3).

Both implementations run it: `FakeMarketDataSync` in unit tests, and
`MarketDataSyncService` — the real one — against a dispatcher that records the
command it would have run. Neither needs a network or a database, because what
this port promises is not *fetching*: it is what happens to a request on its
way in. Fetching is `SyncMarketDataCommand`'s contract, pinned by that
handler's own tests, and duplicating it here would be a second, weaker copy.

**This suite needs one hook**, which is unusual enough to justify. Every
guarantee below is about what the implementation did with the request, and
neither implementation returns it — the fake keeps a list, the service hands a
command to a dispatcher. So a subclass supplies `observed`, a callable
returning the requests as the implementation understood them. The subclass
that wires the real service is where the command-to-request translation lives,
which keeps the asymmetry in the adapter-shaped place rather than in the
contract.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
    MarketDataSyncRequest,
)

_MINUTE = TimeFrame.ONE_MINUTE
_FROM = datetime(2024, 1, 1, tzinfo=UTC)
_TO = datetime(2024, 1, 2, tzinfo=UTC)

#: What a subclass's `observed` fixture returns: the requests the
#: implementation accepted, in order.
type ObservedRequests = Callable[[], list[MarketDataSyncRequest]]


class MarketDataSyncContract:
    """Inherit this, provide `impl` and `observed`. Both must pass all of it."""

    @pytest.fixture
    def impl(self) -> IMarketDataSync:
        raise NotImplementedError(
            "a MarketDataSyncContract subclass must provide an `impl` fixture "
            "returning the IMarketDataSync under test"
        )

    @pytest.fixture
    def observed(self) -> ObservedRequests:
        raise NotImplementedError(
            "a MarketDataSyncContract subclass must provide an `observed` "
            "fixture returning the requests the implementation accepted"
        )

    # -- what the caller asked for arrives intact ----------------------------

    def test_the_interval_and_the_range_arrive_unchanged(
        self, impl: IMarketDataSync, observed: ObservedRequests
    ) -> None:
        """The three fields a caller uses to mean "this window, this cadence".
        A sync that quietly widened or shifted them would fetch data the
        caller did not ask for and bill the rate limit for it."""
        impl.sync(
            MarketDataSyncRequest(
                symbols=("BTCUSDT",),
                interval=TimeFrame.FIVE_MINUTES,
                start_time=_FROM,
                end_time=_TO,
            )
        )

        request = observed()[0]
        assert request.interval == TimeFrame.FIVE_MINUTES
        assert request.start_time == _FROM
        assert request.end_time == _TO

    def test_an_open_ended_request_stays_open_ended(
        self, impl: IMarketDataSync, observed: ObservedRequests
    ) -> None:
        """`None` means "you decide" — the implementation must not turn that
        into a concrete boundary on the way in, or the handler loses the
        distinction between "from the newest stored candle" and "from this
        exact time"."""
        impl.sync(MarketDataSyncRequest(symbols=("BTCUSDT",), interval=_MINUTE))

        request = observed()[0]
        assert request.start_time is None
        assert request.end_time is None

    def test_symbols_are_normalised_to_upper_case(
        self, impl: IMarketDataSync, observed: ObservedRequests
    ) -> None:
        """Every symbol entry point in this app accepts `btcusdt`; the store
        is keyed by `BTCUSDT`. If the port did not normalise, the same symbol
        typed two ways would sync into two shards."""
        impl.sync(
            MarketDataSyncRequest(symbols=("btcusdt", "EthUsdt"), interval=_MINUTE)
        )

        assert observed()[0].symbols == ("BTCUSDT", "ETHUSDT")

    def test_every_symbol_in_one_request_is_kept(
        self, impl: IMarketDataSync, observed: ObservedRequests
    ) -> None:
        impl.sync(
            MarketDataSyncRequest(symbols=("BTCUSDT", "ETHUSDT"), interval=_MINUTE)
        )

        assert observed()[0].symbols == ("BTCUSDT", "ETHUSDT")

    # -- the refusal ---------------------------------------------------------

    def test_an_empty_symbol_list_is_refused(
        self, impl: IMarketDataSync, observed: ObservedRequests
    ) -> None:
        """A screen whose selection is empty must hear about it here, not
        start a sync that fetches nothing and reports success."""
        with pytest.raises(ValueError, match="empty"):
            impl.sync(MarketDataSyncRequest(symbols=(), interval=_MINUTE))

        assert observed() == [], "a refused request must not be started"

    # -- what makes progress attributable -----------------------------------

    def test_a_callers_correlation_id_is_preserved(
        self, impl: IMarketDataSync, observed: ObservedRequests
    ) -> None:
        """`BOT-122`: two screens can legitimately sync the same symbol and
        timeframe at once, and each watches the bus for *its own* progress.
        The id the caller will compare against must survive the trip."""
        impl.sync(
            MarketDataSyncRequest(
                symbols=("BTCUSDT",), interval=_MINUTE, correlation_id="screen-a"
            )
        )

        assert observed()[0].correlation_id == "screen-a"

    def test_a_missing_correlation_id_is_generated_not_left_empty(
        self, impl: IMarketDataSync, observed: ObservedRequests
    ) -> None:
        """A caller that never reads the events still produces them, and an
        event carrying no id cannot be attributed by anyone who does."""
        impl.sync(MarketDataSyncRequest(symbols=("BTCUSDT",), interval=_MINUTE))

        generated = observed()[0].correlation_id
        assert generated, "every started sync carries an id"

    def test_two_callers_ids_are_not_shared(
        self, impl: IMarketDataSync, observed: ObservedRequests
    ) -> None:
        impl.sync(MarketDataSyncRequest(symbols=("BTCUSDT",), interval=_MINUTE))
        impl.sync(MarketDataSyncRequest(symbols=("BTCUSDT",), interval=_MINUTE))

        first, second = observed()
        assert first.correlation_id != second.correlation_id

    # -- cancellation stays the caller's ------------------------------------

    def test_the_callers_cancellation_check_is_passed_through_as_it_is(
        self, impl: IMarketDataSync, observed: ObservedRequests
    ) -> None:
        """Passed through, not copied into a bool: the caller cancels *after*
        the sync starts, so anything that read the flag once on the way in
        would make cancellation impossible (`async-ui-action-rule.md` — the
        caller owns the action)."""
        cancelled = False

        def is_cancelled() -> bool:
            return cancelled

        impl.sync(
            MarketDataSyncRequest(
                symbols=("BTCUSDT",),
                interval=_MINUTE,
                cancellation_requested=is_cancelled,
            )
        )

        forwarded = observed()[0].cancellation_requested
        assert forwarded is not None
        assert forwarded() is False
        cancelled = True
        assert forwarded() is True, "the check must still read the caller's state"

    def test_no_cancellation_check_is_allowed(
        self, impl: IMarketDataSync, observed: ObservedRequests
    ) -> None:
        """Most callers have no token — the CLI, a scheduled job."""
        impl.sync(MarketDataSyncRequest(symbols=("BTCUSDT",), interval=_MINUTE))

        assert observed()[0].cancellation_requested is None

    # -- no opinions of its own ----------------------------------------------

    def test_the_same_request_twice_is_two_syncs(
        self, impl: IMarketDataSync, observed: ObservedRequests
    ) -> None:
        """De-duplication is `InFlightSyncGuard`'s job, downstream and with
        the state to do it right. A port that silently swallowed the second
        ask would make a re-sync after a failure impossible."""
        request = MarketDataSyncRequest(symbols=("BTCUSDT",), interval=_MINUTE)

        impl.sync(request)
        impl.sync(request)

        assert len(observed()) == 2
