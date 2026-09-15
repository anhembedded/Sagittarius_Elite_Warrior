"""`IMarketStream`'s contract, against both implementations (HLD §10.3).

**Where the real half runs, and why here rather than `tests/integration/`.**
The real path is `MarketStreamService` → the dispatcher → the module's two
command handlers → `BinanceWebsocketService`. Everything in that chain except
the last step is pure translation, and the last step's *bookkeeping* — which
owner holds which `(symbol, interval)`, reference-counted — is also pure: the
socket itself lives behind `ITaskManager.spawn`, stubbed here exactly as
`test_binance_websocket_service.py` already stubs it. So the real
subscription logic runs, with nothing to integrate (`ci-rule.md` §6 — the
tier is chosen by what the test touches, not by which class it names).

What that leaves for elsewhere is the socket: reconnect-on-change, the
multiplex key set, ticks reaching the bus. `test_binance_websocket_service.py`
covers those against the same class.

**Why the real half composes the whole chain instead of a fake
`ILiveStreamService`.** Writing one would have been easier and would have
proved nothing: the promises this suite pins — *replace, never add*, *one
owner's release never touches another's* — **are** that service's
reference-counting. Verified against a second fake I wrote myself, both
halves would agree with each other and neither with production.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service import (
    BinanceWebsocketService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.market_stream_service import (
    MarketStreamService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream.handler import (
    StartLiveStreamCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.command import (
    StopLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream.handler import (
    StopLiveStreamCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_live_stream_service import (
    ILiveStreamService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_market_stream import (
    Holdings,
    MarketStreamContract,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)

_MINUTE = TimeFrame.ONE_MINUTE


class _StreamCommandDispatcher:
    """Routes the two stream commands to the real handlers.

    A stand-in for `ICommandDispatcher`, which is a `core/` port owned by
    nobody — so this is not the foreign-port substitution HLD §10.3 rule 4 is
    about, and `test_no_foreign_port_is_mocked.py` permits it by name. It
    routes rather than records, because the guarantees under test live past
    the dispatch.
    """

    def __init__(self, stream_service: ILiveStreamService) -> None:
        self._start = StartLiveStreamCommandHandler(stream_service)
        self._stop = StopLiveStreamCommandHandler(stream_service)

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        if handler_class is StartLiveStreamCommand:
            assert isinstance(input_dto, StartLiveStreamCommand)
            return self._start.execute(input_dto)
        if handler_class is StopLiveStreamCommand:
            assert isinstance(input_dto, StopLiveStreamCommand)
            return self._stop.execute(input_dto)
        raise AssertionError(f"unexpected dispatch: {handler_class}")


class TestFakeMarketStream(MarketStreamContract):
    """The fake's half — what every consumer's test will be driving."""

    @pytest.fixture
    def impl(self) -> IMarketStream:
        return FakeMarketStream()

    @pytest.fixture
    def holdings(self, impl: IMarketStream) -> Holdings:
        assert isinstance(impl, FakeMarketStream)

        def read(owner_id: str) -> tuple[tuple[str, ...], TimeFrame] | None:
            subscription = impl.held_by(owner_id)
            if subscription is None:
                return None
            return subscription.symbols, subscription.interval

        return read


class TestTheRealServiceOverTheRealBookkeeping(MarketStreamContract):
    """The real one's half — this is what makes the fake *verified*."""

    @pytest.fixture
    def websocket_service(self):
        service = BinanceWebsocketService(Mock(), Mock())
        # The socket, and only the socket: `_run_stream` is what
        # `ITaskManager.spawn` would run. Everything the suite asserts on is
        # the bookkeeping above it.
        with patch.object(service, "_run_stream", new=Mock(return_value=Mock())):
            yield service

    @pytest.fixture
    def impl(self, websocket_service) -> IMarketStream:
        return MarketStreamService(_StreamCommandDispatcher(websocket_service))

    @pytest.fixture
    def holdings(self, websocket_service) -> Holdings:
        def read(owner_id: str) -> tuple[tuple[str, ...], TimeFrame] | None:
            """Read off the real registry: `{(symbol, interval): {owners}}`.

            Insertion-ordered, so the symbols come back in the order the
            caller asked for them — the same order the fake reports.
            """
            held = [
                key
                for key, owners in websocket_service._subscriptions.items()
                if owner_id in owners
            ]
            if not held:
                return None
            intervals = {interval for _symbol, interval in held}
            assert len(intervals) == 1, (
                f"{owner_id} holds more than one interval: {intervals} — "
                "`subscribe()` replaces an owner's whole set, so this cannot "
                "happen and the contract's holdings hook would be lying"
            )
            return tuple(symbol for symbol, _ in held), TimeFrame(intervals.pop())

        return read


class TestTheFakesOwnHelpers:
    """`held_by()` and `is_streaming()` — not on the port, so the contract
    suite above cannot cover them.

    `BUG-120`'s guard requires this: a helper a fake adds beyond its port is
    covered by nobody unless its own module tests it, and the "no" cases are
    the ones that matter — a helper that can only say yes is the `Mock` it
    replaced.
    """

    def test_held_by_says_nothing_before_anything_started(self) -> None:
        assert FakeMarketStream().held_by("trading") is None

    def test_held_by_says_nothing_for_an_owner_that_never_started(self) -> None:
        fake = FakeMarketStream()

        fake.start("dashboard", ["BTCUSDT"], _MINUTE)

        assert fake.held_by("trading") is None

    def test_is_streaming_says_no_when_nothing_is(self) -> None:
        assert FakeMarketStream().is_streaming("BTCUSDT") is False

    def test_is_streaming_says_no_for_a_symbol_nobody_asked_for(self) -> None:
        fake = FakeMarketStream()

        fake.start("trading", ["BTCUSDT"], _MINUTE)

        assert fake.is_streaming("ETHUSDT") is False

    def test_is_streaming_says_yes_for_any_owners_symbol(self) -> None:
        fake = FakeMarketStream()

        fake.start("dashboard", ["ETHUSDT"], _MINUTE)

        assert fake.is_streaming("ETHUSDT") is True

    def test_is_streaming_ignores_the_case_the_caller_typed(self) -> None:
        fake = FakeMarketStream()

        fake.start("trading", ["btcusdt"], _MINUTE)

        assert fake.is_streaming("btcusdt") is True
        assert fake.is_streaming("BTCUSDT") is True

    def test_the_interval_narrows_is_streaming(self) -> None:
        fake = FakeMarketStream()

        fake.start("trading", ["BTCUSDT"], _MINUTE)

        assert fake.is_streaming("BTCUSDT", _MINUTE) is True
        assert fake.is_streaming("BTCUSDT", TimeFrame.ONE_DAY) is False

    def test_is_streaming_says_no_after_the_owner_stopped(self) -> None:
        fake = FakeMarketStream()
        fake.start("trading", ["BTCUSDT"], _MINUTE)

        fake.stop("trading")

        assert fake.is_streaming("BTCUSDT") is False

    def test_calls_records_both_verbs_in_order(self) -> None:
        """The surface a consumer asserts "the screen re-subscribed after the
        timeframe changed" against — a fact about the screen, not the socket."""
        fake = FakeMarketStream()

        fake.start("trading", ["BTCUSDT"], _MINUTE)
        fake.start("trading", ["BTCUSDT"], TimeFrame.ONE_DAY)
        fake.stop("trading")

        assert fake.calls == [
            ("start", "trading"),
            ("start", "trading"),
            ("stop", "trading"),
        ]


def test_an_unanswered_dispatch_is_reported_as_a_failure() -> None:
    """`MarketStreamService`'s own rule, and the defect this port was
    published to remove: the call sites used to read
    `getattr(response, "success", True)`, so a dispatcher that answered
    `None` told the user the stream was running."""

    class _AnsweringNothing:
        def dispatch(self, handler_class: type, input_dto: object = None) -> None:
            return None

    service = MarketStreamService(_AnsweringNothing())

    outcome = service.start("trading", ["BTCUSDT"], _MINUTE)

    assert outcome.success is False
    assert outcome.message
