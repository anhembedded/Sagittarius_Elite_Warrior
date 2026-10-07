"""`EPIC-034C` — nothing opens the order session while an Emergency Stop runs.

@details Step 1 closes the session at once; steps 2 and 3 then read the Spot
baseline and the account for seconds. A start, an arm or an order landing in
that window would reconcile "flat", reopen the session and re-baseline the
holdings step 3 sells above (the review of PR #415). The stop marks its run on
the venue's `TradingSessionState`; `SessionReadiness` refuses while it is marked
and `enable()` itself refuses, so a reconciliation that began before the stop
cannot commit after it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop.command import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionBlockReason,
    SessionReadyResult,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.application.session.emergency_stop_builders import (
    make_handler,
    quiet_raw_client,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.recording_publisher import (
    RecordingPublisher,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
)

_FUTURES = TradingVenue.FUTURES_TESTNET


def test_an_opener_arriving_between_step_1_and_step_3_is_refused() -> None:
    state = TradingSessionState()
    state.enable(set())
    readiness = SessionReadiness(
        single_venue_scopes(venue_context(_FUTURES), state), RecordingPublisher()
    )
    asked: list[SessionReadyResult] = []
    raw_client = quiet_raw_client()

    def read_orders_then_an_action_lands(**_: object) -> list:
        asked.append(readiness.ensure_ready(_FUTURES))
        return []

    raw_client.futures_get_open_orders.side_effect = read_orders_then_an_action_lands

    make_handler(session_state=state, raw_client=raw_client).execute(
        EmergencyStopCommand(venue=_FUTURES)
    )

    assert asked  # the stop reads the open orders more than once
    assert {r.block_reason for r in asked} == {
        SessionBlockReason.EMERGENCY_STOP_IN_PROGRESS
    }
    assert state.enabled is False
    assert state.stop_in_progress is False  # cleared once the stop finished


def test_the_mark_is_cleared_even_when_the_stop_raises() -> None:
    state = TradingSessionState()
    raw_client = quiet_raw_client()
    raw_client.futures_get_open_orders.side_effect = RuntimeError("boom")

    make_handler(session_state=state, raw_client=raw_client).execute(
        EmergencyStopCommand(venue=_FUTURES)
    )

    assert state.stop_in_progress is False


def test_enable_refuses_while_a_stop_runs_so_an_earlier_reconciliation_cannot_commit() -> (
    None
):
    state = TradingSessionState()
    state.begin_stop()

    assert state.enable(set()) is False
    assert state.enabled is False

    state.end_stop()
    assert state.enable(set()) is True
