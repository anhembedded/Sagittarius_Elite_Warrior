"""`PRO-014` - `TradingModule.shutdown()` visits only the venues something built.

It used to ask every enabled venue for its context to call `user_data_stream.stop()`, which built
the venue's whole adapter set (and imported the exchange SDK) in a run that never touched the
venue: a `bot list` paid for it on the way out. A venue nobody asked for has no stream to stop.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.trading.composition.venue_contexts import (
    VenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.module import TradingModule
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    venue_context,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET


def _registry(streams: dict[TradingVenue, Mock]) -> tuple[VenueContexts, Mock]:
    """A real registry whose assemblies are stand-ins serving the given streams."""

    def assembly(venue: TradingVenue) -> Mock:
        built = Mock()
        built.context = venue_context(venue, user_data_stream=streams[venue])
        return built

    build = Mock(side_effect=assembly)
    return VenueContexts((_FUTURES, _SPOT), build), build


def _shut_down(contexts: VenueContexts) -> None:
    container = StdLibContainer()
    container.singleton(IInstanceAccess, InstanceAccess.unguarded())
    container.singleton(IVenueContexts, contexts)
    TradingModule().shutdown(SimpleNamespace(container=container))


def test_a_registry_that_nobody_asked_builds_nothing_on_shutdown() -> None:
    streams = {_FUTURES: Mock(spec=IUserDataStream), _SPOT: Mock(spec=IUserDataStream)}
    contexts, build = _registry(streams)

    _shut_down(contexts)

    build.assert_not_called()
    streams[_FUTURES].stop.assert_not_called()
    streams[_SPOT].stop.assert_not_called()


def test_only_the_venue_something_asked_for_is_built_and_stopped() -> None:
    streams = {_FUTURES: Mock(spec=IUserDataStream), _SPOT: Mock(spec=IUserDataStream)}
    contexts, build = _registry(streams)
    contexts.get(_SPOT)

    _shut_down(contexts)

    assert contexts.built() == (_SPOT,)
    assert [call.args[0] for call in build.call_args_list] == [_SPOT]
    streams[_SPOT].stop.assert_called_once_with()
    streams[_FUTURES].stop.assert_not_called()
