"""`EPIC-029` ADR D7 — a venue's trading switch publishes
`TradingSwitchChangedEvent` once per change, at the moment it changes.

@details A bot pauses on the moment trading turns off, not on its next
refused order. The three handlers that move the switch are built the way
their own test files build them, with a recording publisher derived from
`IEventPublisher` (`testing-rule.md` §2).
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.session.disable_trading import (
    DisableTradingCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.enable_trading import (
    EnableTradingCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.session.emergency_stop_builders import (
    make_handler,
    quiet_raw_client,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.session.test_disable_trading import (
    _handler as _disable_handler,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.session.test_enable_trading import (
    _handler as _enable_handler,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.session.test_enable_trading import (
    _position_payload,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
)
from sagittarius_engine.domain.i_domain_event import IDomainEvent

_FUTURES = TradingVenue.FUTURES_TESTNET


def _switch(publisher: RecordingPublisher) -> tuple[TradingVenue, bool, object]:
    (event,) = publisher.of_type(TradingSwitchChangedEvent)
    return event.venue, event.enabled, event.cause


def _enabled_state() -> TradingSessionState:
    state = TradingSessionState()
    state.enable(set())
    return state


def test_a_committed_enable_publishes_enabled() -> None:
    publisher = RecordingPublisher()
    handler, state, _, _ = _enable_handler(publisher=publisher)

    handler.execute(EnableTradingCommand(venue=_FUTURES))

    assert state.enabled is True
    assert _switch(publisher) == (_FUTURES, True, TradingSwitchCause.ENABLED)


def test_a_refused_enable_publishes_nothing() -> None:
    publisher = RecordingPublisher()
    handler, _, _, _ = _enable_handler(
        position_payloads=[_position_payload()], publisher=publisher
    )

    handler.execute(EnableTradingCommand(venue=_FUTURES))

    assert publisher.events == []


def test_disabling_an_enabled_venue_publishes_disabled() -> None:
    publisher = RecordingPublisher()
    handler, _, _ = _disable_handler(_enabled_state(), publisher)

    handler.execute(DisableTradingCommand(venue=_FUTURES))

    assert _switch(publisher) == (_FUTURES, False, TradingSwitchCause.DISABLED)


def test_disabling_a_venue_that_was_off_publishes_nothing() -> None:
    """Only a real change is news; a second disable is not."""
    publisher = RecordingPublisher()
    handler, _, _ = _disable_handler(publisher=publisher)

    handler.execute(DisableTradingCommand(venue=_FUTURES))

    assert publisher.events == []


class _OrderedPublisher(RecordingPublisher):
    def __init__(self, call_order: list[str]) -> None:
        super().__init__()
        self._call_order = call_order

    def publish(self, event: IDomainEvent) -> None:
        super().publish(event)
        self._call_order.append("switch_event")


def test_an_emergency_stop_publishes_at_step_1_before_the_cancels() -> None:
    """Published right after the disable and before any order is read or
    cancelled, so a bot never misreads the stop's cancels as a fault."""
    call_order: list[str] = []
    state = _enabled_state()
    original_disable = state.disable

    def _record_disable() -> None:
        call_order.append("disable")
        original_disable()

    state.disable = _record_disable  # type: ignore[method-assign]
    raw_client = quiet_raw_client()
    raw_client.futures_get_open_orders.side_effect = lambda **_: (
        call_order.append("read_orders") or []
    )
    publisher = _OrderedPublisher(call_order)

    make_handler(
        session_state=state, raw_client=raw_client, publisher=publisher
    ).execute(EmergencyStopCommand(venue=_FUTURES))

    assert call_order[:3] == ["disable", "switch_event", "read_orders"]
    assert _switch(publisher) == (
        _FUTURES,
        False,
        TradingSwitchCause.EMERGENCY_STOP,
    )


def test_an_emergency_stop_on_a_venue_already_off_still_publishes() -> None:
    """The stop cancels and sells whatever the switch said, so a bot whose
    orders it is about to cancel is told even when trading was off."""
    publisher = RecordingPublisher()

    make_handler(raw_client=quiet_raw_client(), publisher=publisher).execute(
        EmergencyStopCommand(venue=_FUTURES)
    )

    assert _switch(publisher) == (
        _FUTURES,
        False,
        TradingSwitchCause.EMERGENCY_STOP,
    )


def test_a_failed_disable_publishes_nothing() -> None:
    """The event reports a switch that changed; a disable that raised did
    not change it, and step 1 reports the failure on its own."""
    session_state = Mock()
    session_state.disable.side_effect = RuntimeError("boom")
    publisher = RecordingPublisher()

    result = make_handler(
        session_state=session_state,
        raw_client=quiet_raw_client(),
        publisher=publisher,
    ).execute(EmergencyStopCommand(venue=_FUTURES))

    assert result.trading_disabled.succeeded is False
    assert publisher.events == []
