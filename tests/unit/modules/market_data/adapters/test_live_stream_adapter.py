"""`PRO-014` - the hosted live-stream adapter stops a stream only if something built one.

It used to take the stream service in its constructor, so every boot built the websocket
service and imported the exchange SDK for a run that never opened a stream.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.live_stream_adapter import (
    LiveStreamEngineAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_live_stream_service import (
    ILiveStreamService,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer


def _context(container: StdLibContainer) -> Mock:
    context = Mock()
    context.container = container
    return context


def test_a_stream_nobody_built_is_not_built_to_be_stopped() -> None:
    built: list[object] = []
    container = StdLibContainer()
    container.singleton(ILiveStreamService, lambda _: built.append(1) or Mock())

    LiveStreamEngineAdapter().stop(_context(container))

    assert built == []


def test_a_stream_that_was_built_is_stopped() -> None:
    service = Mock(spec=ILiveStreamService)
    container = StdLibContainer()
    container.singleton(ILiveStreamService, lambda _: service)
    container.resolve(ILiveStreamService)

    LiveStreamEngineAdapter().stop(_context(container))

    service.stop_all.assert_called_once_with()


def test_stopping_with_no_stream_bound_at_all_does_nothing() -> None:
    LiveStreamEngineAdapter().stop(_context(StdLibContainer()))
