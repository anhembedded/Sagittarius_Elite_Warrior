"""`EPIC-028B` — `TradingModule.shutdown()` closes every enabled venue's
user-data stream, not only the primary venue's.

@details With Futures and Spot live together, a session may have enabled
trading on either or both; each has its own socket. The streams are
`Mock(spec=IUserDataStream)` (trading's own port in trading's own test) so
the test sees which were asked to stop; the registry is the verified
`FakeVenueContexts`.
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.module import TradingModule
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    venue_context,
)
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer


def _shut_down(futures: Mock, spot: Mock) -> None:
    container = StdLibContainer()
    container.singleton(IInstanceAccess, InstanceAccess.unguarded())
    container.singleton(
        IVenueContexts,
        FakeVenueContexts(
            venue_context(TradingVenue.FUTURES_TESTNET, user_data_stream=futures),
            venue_context(TradingVenue.SPOT_TESTNET, user_data_stream=spot),
        ),
    )
    TradingModule().shutdown(SimpleNamespace(container=container))


def test_every_enabled_venues_stream_is_stopped() -> None:
    futures = Mock(spec=IUserDataStream)
    spot = Mock(spec=IUserDataStream)

    _shut_down(futures, spot)

    futures.stop.assert_called_once_with()
    spot.stop.assert_called_once_with()


def test_one_stream_failing_to_close_does_not_leave_the_other_open() -> None:
    futures = Mock(spec=IUserDataStream)
    futures.stop.side_effect = RuntimeError("socket already gone")
    spot = Mock(spec=IUserDataStream)

    _shut_down(futures, spot)

    spot.stop.assert_called_once_with()
