"""`EPIC-034C` — `SessionReadiness` opens the order session once and leaves it
open.

@details The first deliberate action reconciles the account and opens the
session; the second finds it open and asks the venue nothing, so it neither
refuses on the first action's positions nor clears a bot's budget; an Emergency
Stop closes it, and the next action reconciles again. The refusals and the
baseline are `test_ensure_session_ready.py`'s.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.application.session.ensure_session_ready import (
    EnsureSessionReadyCommand,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.session.test_ensure_session_ready import (
    _handler,
    _position_payload,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
)


def test_a_session_that_is_open_is_not_reconciled_again() -> None:
    """`EPIC-034C` — the second action finds the session open: it asks the
    venue nothing, opens no second stream and clears no bot's budget. A
    reconciliation here would refuse on the positions the first action opened."""
    handler, session_state, user_data_stream, account_reader = _handler(
        position_payloads=[_position_payload()]
    )
    session_state.enable(set())
    generation = session_state.generation
    epoch = session_state.switch_epoch

    result = handler.execute(
        EnsureSessionReadyCommand(venue=TradingVenue.FUTURES_TESTNET)
    )

    assert result.ready is True
    assert result.already_open is True
    assert result.account_was_read is False
    account_reader.check_connection.assert_not_called()
    user_data_stream.start.assert_not_called()
    assert (session_state.generation, session_state.switch_epoch) == (generation, epoch)


def test_the_first_action_opens_the_session_and_says_so_on_the_bus() -> None:
    publisher = RecordingPublisher()
    handler, _state, _stream, _reader = _handler(publisher=publisher)

    handler.execute(EnsureSessionReadyCommand(venue=TradingVenue.FUTURES_TESTNET))
    handler.execute(EnsureSessionReadyCommand(venue=TradingVenue.FUTURES_TESTNET))

    assert len(publisher.events) == 1  # opened once; the second call was a no-op


def test_after_an_emergency_stop_the_next_action_reconciles_again() -> None:
    """The stop closes the session; only a deliberate action reopens it, and it
    reads the account again rather than trusting the earlier answer."""
    handler, session_state, user_data_stream, account_reader = _handler()
    handler.execute(EnsureSessionReadyCommand(venue=TradingVenue.FUTURES_TESTNET))
    session_state.disable()  # what Emergency Stop's step 1 does

    result = handler.execute(
        EnsureSessionReadyCommand(venue=TradingVenue.FUTURES_TESTNET)
    )

    assert result.ready is True
    assert result.already_open is False
    assert account_reader.check_connection.call_count == 2
    assert user_data_stream.start.call_count == 2
