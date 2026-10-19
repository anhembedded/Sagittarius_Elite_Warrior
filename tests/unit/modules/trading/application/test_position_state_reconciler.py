from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_position_book import (
    OwnerPositionBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.position_state_reconciler import (
    reconcile_position_state,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    EMPTY_POSITION,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.owner_position_world import (
    REGISTRATION,
    STEP,
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


def _logged_warnings(run: Callable[[], None]) -> list[str]:
    """What `run` made `App.LiveTradingCoordinator` say at WARNING or worse; the `App.*`
    loggers do not propagate to `caplog`."""
    lines: list[str] = []

    class _Keep(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(record.getMessage())

    handler = _Keep(logging.WARNING)
    logger = logging.getLogger("App.LiveTradingCoordinator")
    logger.addHandler(handler)
    try:
        run()
    finally:
        logger.removeHandler(handler)
    return lines


def test_a_budgeted_owners_position_learned_from_the_exchange_is_not_a_warning() -> (
    None
):
    """`BUG-203`: an owner's order never marks the symbol open, so the exchange's first
    report of its position corrects a belief nobody held."""
    state = TradingSessionState()
    state.owner_books.install(
        "tag", OwnerPositionBook(REGISTRATION, EMPTY_POSITION, STEP)
    )

    warned = _logged_warnings(
        lambda: reconcile_position_state(state, REGISTRATION.symbol, has_position=True)
    )

    assert state.open_position_count(REGISTRATION.symbol) == 1
    assert warned == []


def test_a_symbol_no_owner_trades_still_warns_when_the_belief_was_wrong() -> None:
    state = TradingSessionState()
    state.owner_books.install(
        "tag", OwnerPositionBook(REGISTRATION, EMPTY_POSITION, STEP)
    )

    warned = _logged_warnings(
        lambda: reconcile_position_state(state, "SOLUSDT", has_position=True)
    )

    assert len(warned) == 1
