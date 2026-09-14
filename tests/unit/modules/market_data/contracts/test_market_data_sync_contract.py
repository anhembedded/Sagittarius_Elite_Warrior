"""`IMarketDataSync`'s contract, against both implementations (HLD §10.3).

**Both halves are unit tests, and that is deliberate.** For
`IMarketDataRepository` the real side runs in `tests/integration/` because the
real implementation is SQLite — there is I/O to be wrong about. This port's
real implementation is `MarketDataSyncService`, whose whole job is to turn a
published request into the module's own command and dispatch it: no file, no
socket, nothing to integrate. Putting it in `tests/integration/` would buy a
slower tier and no extra truth (`ci-rule.md` §6 — the tier is chosen by what
the test touches, not by which class it names).

What the *handler* then does with that command — fetching, resuming from the
newest stored candle, publishing progress — is `SyncMarketDataCommand`'s own
contract, and it already has tests at the tier that can prove it.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.market_data_sync_service import (
    MarketDataSyncService,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.sync_market_data import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_market_data_sync import (
    MarketDataSyncContract,
    ObservedRequests,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)


class _RecordingDispatcher:
    """Captures the command instead of running it.

    A stand-in for `ICommandDispatcher`, which is a `core/` port owned by
    nobody — so this is not the foreign-port substitution HLD §10.3 rule 4 is
    about, and `test_no_foreign_port_is_mocked.py` permits it by name.
    """

    def __init__(self) -> None:
        self.commands: list[SyncMarketDataCommand] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        assert handler_class is SyncMarketDataCommand
        assert isinstance(input_dto, SyncMarketDataCommand)
        self.commands.append(input_dto)
        return None


class TestFakeMarketDataSync(MarketDataSyncContract):
    """The fake's half — what every consumer's test will be driving."""

    @pytest.fixture
    def impl(self) -> IMarketDataSync:
        return FakeMarketDataSync()

    @pytest.fixture
    def observed(self, impl: IMarketDataSync) -> ObservedRequests:
        assert isinstance(impl, FakeMarketDataSync)
        return lambda: impl.requests


class TestMarketDataSyncService(MarketDataSyncContract):
    """The real one's half — this is what makes the fake *verified*."""

    @pytest.fixture
    def dispatcher(self) -> _RecordingDispatcher:
        return _RecordingDispatcher()

    @pytest.fixture
    def impl(self, dispatcher: _RecordingDispatcher) -> IMarketDataSync:
        return MarketDataSyncService(dispatcher)

    @pytest.fixture
    def observed(self, dispatcher: _RecordingDispatcher) -> ObservedRequests:
        """The commands the service dispatched, read back as requests.

        The translation lives here rather than in the suite because it is the
        asymmetry between the two implementations: the fake keeps requests,
        the service produces commands. Everything the contract asserts is a
        field both shapes carry, so the mapping is mechanical.
        """

        def as_requests() -> list[MarketDataSyncRequest]:
            return [
                MarketDataSyncRequest(
                    symbols=tuple(command.symbols),
                    interval=command.interval,
                    start_time=command.start_time,
                    end_time=command.end_time,
                    cancellation_requested=command.cancellation_requested,
                    correlation_id=command.correlation_id,
                )
                for command in dispatcher.commands
            ]

        return as_requests


def test_the_service_dispatches_the_modules_own_command() -> None:
    """The one thing the contract cannot say, because it is about *how* this
    implementation keeps its promise: one sync is one `SyncMarketDataCommand`
    through the dispatcher, so the in-flight guard and the progress events —
    which live in the handler, not here — stay on the only path they know."""
    dispatcher = _RecordingDispatcher()

    MarketDataSyncService(dispatcher).sync(
        MarketDataSyncRequest(symbols=("BTCUSDT",), interval="1m")
    )

    assert len(dispatcher.commands) == 1
