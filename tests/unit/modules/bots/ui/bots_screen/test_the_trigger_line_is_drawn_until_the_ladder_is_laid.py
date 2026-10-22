"""`EPIC-046B` (ADR 046 D3, D5) - the Bots screen draws the plan's trigger line until it latches.

The overlay is the plan's and always holds the line; the screen leaves it out once the bot has laid,
is laying or is taking down its ladder, as a filled limit order is not redrawn. A bot whose next
Start, or Resume while it holds nothing, asks the trigger again keeps it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    BotOverlay,
    OverlayLine,
    OverlayRole,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_trigger_line import (
    shown_for,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

S = BotLifecycleState
_OVERLAY = BotOverlay(
    lines=(
        OverlayLine(Decimal(100), OverlayRole.BUY_LEVEL, "L0"),
        OverlayLine(Decimal(125), OverlayRole.TRIGGER, "Trigger ≤ 125"),
        OverlayLine(Decimal(140), OverlayRole.SELL_LEVEL, "L1"),
    )
)


def _bot(state: S, recovering_from: S | None = None) -> BotSnapshot:
    return BotSnapshot(
        bot_id="a3f9c1",
        name="grid",
        kind="grid",
        venue=TradingVenue.SPOT_TESTNET,
        symbol="BTCUSDT",
        state=state,
        created_at=datetime(2026, 10, 22, tzinfo=UTC),
        run_started_at=None,
        config={},
        recovering_from=recovering_from,
    )


def _roles(overlay: BotOverlay | None) -> list[OverlayRole]:
    assert overlay is not None
    return [line.role for line in overlay.lines]


@pytest.mark.parametrize(
    "state",
    [S.DRAFT, S.STOPPED, S.AWAITING_RANGE, S.HALTED, S.AWAITING_RECOVERY, S.ERROR],
    ids=lambda s: s.value,
)
def test_a_bot_whose_next_entry_asks_the_trigger_keeps_the_line(state: S) -> None:
    assert OverlayRole.TRIGGER in _roles(shown_for(_OVERLAY, _bot(state)))


@pytest.mark.parametrize(
    "state", [S.STARTING, S.RUNNING, S.PAUSED, S.STOPPING], ids=lambda s: s.value
)
def test_a_bot_that_laid_its_ladder_draws_no_trigger_line_and_keeps_the_rest(
    state: S,
) -> None:
    roles = _roles(shown_for(_OVERLAY, _bot(state)))

    assert OverlayRole.TRIGGER not in roles
    assert roles == [OverlayRole.BUY_LEVEL, OverlayRole.SELL_LEVEL]


def test_a_recovering_bot_is_judged_by_the_state_it_returns_to() -> None:
    returns_running = _bot(S.RECOVERING, S.RUNNING)
    returns_waiting = replace(returns_running, recovering_from=S.AWAITING_RANGE)

    assert OverlayRole.TRIGGER not in _roles(shown_for(_OVERLAY, returns_running))
    assert OverlayRole.TRIGGER in _roles(shown_for(_OVERLAY, returns_waiting))


def test_no_overlay_stays_none() -> None:
    assert shown_for(None, _bot(S.RUNNING)) is None


def _holding(inventory: str = "0", open_orders: int = 0) -> BotProgress:
    return BotProgress(
        realised_profit=Decimal(0),
        completed_cycles=0,
        open_orders=open_orders,
        inventory=Decimal(inventory),
        average_cost=None,
        reason="",
        reason_detail="",
    )


@pytest.mark.parametrize(
    "state", [S.HALTED, S.AWAITING_RECOVERY, S.ERROR], ids=lambda s: s.value
)
@pytest.mark.parametrize(
    ("progress", "drawn"),
    [
        (_holding("0.5"), False),
        (_holding(open_orders=3), False),
        (_holding(), True),
    ],
    ids=["holds-inventory", "holds-orders", "holds-nothing"],
)
def test_a_halted_bot_is_judged_by_what_its_record_holds(
    state: S, progress: BotProgress, drawn: bool
) -> None:
    """Review of #725: its Resume plans over what it holds and asks the trigger only when flat."""
    bot = replace(_bot(state), progress=progress)

    assert (OverlayRole.TRIGGER in _roles(shown_for(_OVERLAY, bot))) is drawn
