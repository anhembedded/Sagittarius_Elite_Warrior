from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.application.services.position_state_reconciler import (
    reconcile_position_state,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)


def test_agreement_updates_state_silently(caplog) -> None:
    state = TradingSessionState()
    state.enable({"BTCUSDT"})

    with caplog.at_level(logging.WARNING):
        reconcile_position_state(state, "BTCUSDT", has_position=True)

    assert state.open_position_count("BTCUSDT") == 1
    assert caplog.records == []


def test_exchange_wins_when_app_thought_flat_but_exchange_has_a_position(
    caplog,
) -> None:
    """`EPIC-021H` §2.4's own example: app believed `NEW`/flat, exchange
    reports otherwise — the exchange wins, and the mismatch is logged."""
    state = TradingSessionState()

    with caplog.at_level(logging.WARNING):
        reconcile_position_state(state, "BTCUSDT", has_position=True)

    assert state.open_position_count("BTCUSDT") == 1
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING


def test_exchange_wins_when_app_thought_open_but_exchange_is_flat(caplog) -> None:
    state = TradingSessionState()
    state.enable({"BTCUSDT"})

    with caplog.at_level(logging.WARNING):
        reconcile_position_state(state, "BTCUSDT", has_position=False)

    assert state.open_position_count("BTCUSDT") == 0
    assert len(caplog.records) == 1
