"""The contract suite for `IMarketStream` (HLD §10.3).

Both implementations run it: `FakeMarketStream`, and the real
`MarketStreamService` over the module's two command handlers and a fake
`ILiveStreamService`. Neither needs a socket, because what this port
promises is not *bytes arriving* — it is the subscription bookkeeping
`BOT-126` introduced: an owner's set is replaced, not added to, and one
owner's release never touches another's. Bytes arriving is
`BinanceWebsocketService`'s own contract.

**The suite needs one hook.** The guarantees are about who holds what, and
neither implementation returns that from `start()`: the fake keeps a dict,
and the real service hands a command to a dispatcher that ends at a
reference-counted service. So a subclass supplies `holdings`, a callable
answering "which symbols does this owner hold, at which interval" — and the
subclass wiring the real service is where the answer is read off
`ILiveStreamService`, which keeps the asymmetry in the adapter-shaped place
rather than in the contract.

What this suite does **not** pin is the wording of `StreamOutcome.message`: a
message is for a user, and a test asserting on prose would break on a
rewording that changed no promise. `success` is the promise.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)

_MINUTE = TimeFrame.ONE_MINUTE
_DAY = TimeFrame.ONE_DAY

#: What a subclass's `holdings` fixture returns: for one owner, the symbols
#: it currently streams paired with the interval, or `None` when it holds
#: nothing at all. `None` and `()` are different answers and the suite
#: checks both.
type Holdings = Callable[[str], tuple[tuple[str, ...], TimeFrame] | None]


class MarketStreamContract:
    """Inherit this, provide `impl` and `holdings`. Both must pass all of it."""

    @pytest.fixture
    def impl(self) -> IMarketStream:
        raise NotImplementedError(
            "a MarketStreamContract subclass must provide an `impl` fixture "
            "returning the IMarketStream under test"
        )

    @pytest.fixture
    def holdings(self) -> Holdings:
        raise NotImplementedError(
            "a MarketStreamContract subclass must provide a `holdings` "
            "fixture answering what one owner currently streams"
        )

    # -- starting ------------------------------------------------------------

    def test_starting_makes_the_owner_hold_exactly_what_was_asked_for(
        self, impl: IMarketStream, holdings: Holdings
    ) -> None:
        outcome = impl.start("trading", ["BTCUSDT", "ETHUSDT"], _MINUTE)

        assert outcome.success is True
        assert holdings("trading") == (("BTCUSDT", "ETHUSDT"), _MINUTE)

    def test_symbols_are_upper_cased(
        self, impl: IMarketStream, holdings: Holdings
    ) -> None:
        """Every symbol entry point in this app normalises, so a caller
        passing what a user typed is not a near miss that streams nothing."""
        impl.start("trading", ["btcusdt"], _MINUTE)

        assert holdings("trading") == (("BTCUSDT",), _MINUTE)

    def test_an_empty_symbol_list_is_refused(self, impl: IMarketStream) -> None:
        """Not a quiet no-op: an empty subscription set cannot be told apart
        from a stream that stopped, so a screen that reached here with
        nothing selected must hear about it."""
        with pytest.raises(ValueError):
            impl.start("trading", [], _MINUTE)

    def test_an_empty_owner_is_refused(self, impl: IMarketStream) -> None:
        with pytest.raises(ValueError):
            impl.start("   ", ["BTCUSDT"], _MINUTE)

    # -- replacing, which is the whole point of BOT-126 ----------------------

    def test_starting_again_replaces_that_owners_set_instead_of_adding(
        self, impl: IMarketStream, holdings: Holdings
    ) -> None:
        """How a screen changes symbol: it starts again. Adding instead would
        leave the old symbol streaming forever, which is the leak `BOT-126`
        replaced `start_stream()` to fix."""
        impl.start("trading", ["BTCUSDT"], _MINUTE)
        impl.start("trading", ["ETHUSDT"], _MINUTE)

        assert holdings("trading") == (("ETHUSDT",), _MINUTE)

    def test_starting_again_replaces_the_interval_too(
        self, impl: IMarketStream, holdings: Holdings
    ) -> None:
        impl.start("trading", ["BTCUSDT"], _MINUTE)
        impl.start("trading", ["BTCUSDT"], _DAY)

        assert holdings("trading") == (("BTCUSDT",), _DAY)

    # -- two owners, which is the other half ---------------------------------

    def test_two_owners_hold_their_own_sets_at_once(
        self, impl: IMarketStream, holdings: Holdings
    ) -> None:
        """`BUG-085`: the trading chart and the Dev Board are two owners, and
        before `BOT-126` whichever started last decided what every screen
        received."""
        impl.start("trading", ["BTCUSDT"], _MINUTE)
        impl.start("dashboard", ["ETHUSDT"], _DAY)

        assert holdings("trading") == (("BTCUSDT",), _MINUTE)
        assert holdings("dashboard") == (("ETHUSDT",), _DAY)

    def test_two_owners_may_hold_the_same_symbol(
        self, impl: IMarketStream, holdings: Holdings
    ) -> None:
        """An owner id is a namespace, not a lease
        (`Docs/VOCABULARY/README.md`): the second caller is not refused."""
        impl.start("trading", ["BTCUSDT"], _MINUTE)
        outcome = impl.start("dashboard", ["BTCUSDT"], _MINUTE)

        assert outcome.success is True
        assert holdings("trading") == (("BTCUSDT",), _MINUTE)
        assert holdings("dashboard") == (("BTCUSDT",), _MINUTE)

    # -- stopping ------------------------------------------------------------

    def test_stopping_releases_that_owners_whole_set(
        self, impl: IMarketStream, holdings: Holdings
    ) -> None:
        impl.start("trading", ["BTCUSDT", "ETHUSDT"], _MINUTE)

        outcome = impl.stop("trading")

        assert outcome.success is True
        assert holdings("trading") is None

    def test_stopping_one_owner_leaves_the_other_streaming(
        self, impl: IMarketStream, holdings: Holdings
    ) -> None:
        """Even for the same pair — which is what reference counting buys and
        what a screen closing must not take from the other screen."""
        impl.start("trading", ["BTCUSDT"], _MINUTE)
        impl.start("dashboard", ["BTCUSDT"], _MINUTE)

        impl.stop("trading")

        assert holdings("trading") is None
        assert holdings("dashboard") == (("BTCUSDT",), _MINUTE)

    def test_stopping_what_was_never_started_says_so_without_raising(
        self, impl: IMarketStream
    ) -> None:
        """An ordinary state, not an error: the trading chart's `stop()` is
        unconditional by design and its caller decides when it is safe to
        call at all."""
        outcome = impl.stop("trading")

        assert outcome.success is False
        assert outcome.message

    def test_stopping_twice_is_idempotent(
        self, impl: IMarketStream, holdings: Holdings
    ) -> None:
        impl.start("trading", ["BTCUSDT"], _MINUTE)

        assert impl.stop("trading").success is True
        assert impl.stop("trading").success is False
        assert holdings("trading") is None

    def test_an_owner_can_start_again_after_stopping(
        self, impl: IMarketStream, holdings: Holdings
    ) -> None:
        """A screen the user closed and reopened, which is the ordinary
        lifecycle and must not need a new owner id."""
        impl.start("trading", ["BTCUSDT"], _MINUTE)
        impl.stop("trading")

        impl.start("trading", ["ETHUSDT"], _MINUTE)

        assert holdings("trading") == (("ETHUSDT",), _MINUTE)

    # -- the outcome is a named type -----------------------------------------

    def test_every_outcome_carries_both_fields(self, impl: IMarketStream) -> None:
        """The reason this port exists at all: the callers used to read
        `getattr(response, "success", True)`, which reports success for an
        object that has no such field."""
        started = impl.start("trading", ["BTCUSDT"], _MINUTE)
        stopped = impl.stop("trading")

        for outcome in (started, stopped):
            assert isinstance(outcome.success, bool)
            assert isinstance(outcome.message, str)
