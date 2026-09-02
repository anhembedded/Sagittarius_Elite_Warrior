from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.disable_trading import (
    DisableTradingCommand,
    DisableTradingCommandHandler,
)


def _handler(
    session_state: TradingSessionState | None = None,
) -> tuple[DisableTradingCommandHandler, TradingSessionState, Mock]:
    session_state = session_state or TradingSessionState()
    user_data_stream = Mock()
    return (
        DisableTradingCommandHandler(session_state, user_data_stream),
        session_state,
        user_data_stream,
    )


def test_disables_a_session_that_was_enabled() -> None:
    session_state = TradingSessionState()
    session_state.enable({"BTCUSDT"})
    handler, session_state, user_data_stream = _handler(session_state)

    handler.execute(DisableTradingCommand())

    assert session_state.enabled is False
    user_data_stream.stop.assert_called_once()


def test_disabling_an_already_disabled_session_is_a_no_op_but_still_stops_the_stream() -> (
    None
):
    """`IUserDataStream.stop()` is itself a no-op when nothing is running
    (its own contract), so calling it unconditionally is safe — this closes
    the case where `enabled` was already `False` (app just booted, or a
    prior disable never got its `stop()` through, e.g. a crash)."""
    handler, session_state, user_data_stream = _handler()

    handler.execute(DisableTradingCommand())

    assert session_state.enabled is False
    user_data_stream.stop.assert_called_once()


def test_symmetric_with_enable_known_open_symbols_survive_disable() -> None:
    """Disabling must not silently wipe `known_open_symbols` — that set is
    this app's own bookkeeping of what it believes is open, independent of
    the enabled flag, and the next `EnableTradingCommand` reconciles it
    against the exchange fresh regardless."""
    session_state = TradingSessionState()
    session_state.enable({"BTCUSDT"})
    handler, session_state, _ = _handler(session_state)

    handler.execute(DisableTradingCommand())

    assert session_state.known_open_symbols == {"BTCUSDT"}
