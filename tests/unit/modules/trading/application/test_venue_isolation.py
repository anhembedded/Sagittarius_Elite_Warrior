"""`EPIC-028B` — with both venues live, a command addressed to one venue
touches only that venue: its session state, its client, its user data stream.

@details The acceptance criterion this pins: *"Emergency Stop on Futures
leaves Spot's session, orders and baseline untouched, and vice versa."*
Both venues are served by one `VenueTradingScopes`, exactly as in the
running app; each venue's ports are specced mocks of trading's own ports,
so a call reaching the wrong venue is visible as a call on that mock.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.preview_order import (
    PreviewOrderQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.submit_order import (
    SubmitOrderCommand,
    SubmitOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.disable_trading import (
    DisableTradingCommand,
    DisableTradingCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop import (
    EmergencyStopCommand,
    EmergencyStopCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    venue_context,
    venue_scopes,
)

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET


class _Venue:
    """One venue's collaborators, arranged so a test can see whether they
    were touched."""

    def __init__(self, venue: TradingVenue) -> None:
        self.state = TradingSessionState()
        self.state.enable(set(), spot_baseline_holdings={"BTC": Decimal(1)})
        self.client = Mock(spec=ITradingClient)
        self.client.get_open_orders.return_value = []
        self.client.get_positions.return_value = []
        self.client_factory = Mock(spec=ITradingClientFactory)
        self.client_factory.create.return_value = self.client
        self.stream = Mock(spec=IUserDataStream)
        self.account_reader = FakeTradingAccountReader(
            ExchangeConnectionStatus(
                venue=venue,
                reachable=True,
                failure=None,
                server_time_skew_ms=0,
                usdt_balance=Decimal(1000),
                position_mode=None,
                margin_type=None,
                open_position_count=0,
                holdings=(),
            )
        )
        self.context = venue_context(
            venue,
            account_reader=self.account_reader,
            client_factory=self.client_factory,
            user_data_stream=self.stream,
        )


def _both() -> tuple[_Venue, _Venue, dict[TradingVenue, TradingSessionState]]:
    futures, spot = _Venue(_FUTURES), _Venue(_SPOT)
    return futures, spot, {_FUTURES: futures.state, _SPOT: spot.state}


def _assert_untouched(venue: _Venue) -> None:
    assert venue.state.enabled is True
    assert venue.state.spot_baseline_holdings() == {"BTC": Decimal(1)}
    venue.client_factory.create.assert_not_called()
    venue.stream.stop.assert_not_called()


@pytest.mark.parametrize(("stopped", "kept"), [(_FUTURES, _SPOT), (_SPOT, _FUTURES)])
def test_an_emergency_stop_on_one_venue_leaves_the_other_untouched(
    stopped: TradingVenue, kept: TradingVenue
) -> None:
    futures, spot, states = _both()
    by_venue = {_FUTURES: futures, _SPOT: spot}
    handler = EmergencyStopCommandHandler(
        venue_scopes(futures.context, spot.context, session_states=states)
    )

    handler.execute(EmergencyStopCommand(venue=stopped))

    assert by_venue[stopped].state.enabled is False
    by_venue[stopped].stream.stop.assert_called_once_with()
    by_venue[stopped].client_factory.create.assert_called_once()
    _assert_untouched(by_venue[kept])


def test_disabling_one_venue_leaves_the_other_trading() -> None:
    futures, spot, states = _both()
    handler = DisableTradingCommandHandler(
        venue_scopes(futures.context, spot.context, session_states=states)
    )

    handler.execute(DisableTradingCommand(venue=_SPOT))

    assert spot.state.enabled is False
    _assert_untouched(futures)


def test_a_command_for_a_venue_that_is_not_served_is_refused() -> None:
    """Only Futures is configured: a Spot command is a wiring bug, and it
    fails before any state is created for Spot."""
    futures = _Venue(_FUTURES)
    handler = DisableTradingCommandHandler(
        venue_scopes(futures.context, session_states={_FUTURES: futures.state})
    )

    with pytest.raises(VenueNotEnabledError, match="spot_testnet"):
        handler.execute(DisableTradingCommand(venue=_SPOT))
    _assert_untouched(futures)


def test_validating_an_order_on_a_venue_that_cannot_trade_raises() -> None:
    """Replaces the unbound `ITradingClient` a `DISABLED` process used to
    raise at dispatch time: the refusal is now named, and nothing is built."""
    disabled = venue_context(TradingVenue.DISABLED)
    preview_handler = Mock()
    handler = SubmitOrderCommandHandler(preview_handler, FakeVenueContexts(disabled))
    command = SubmitOrderCommand(
        order_request=PreviewOrderQuery(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.002"),
            reference_price=Decimal(64000),
            venue=TradingVenue.DISABLED,
        )
    )

    with pytest.raises(VenueNotEnabledError):
        handler.execute(command)
    preview_handler.execute.assert_not_called()
