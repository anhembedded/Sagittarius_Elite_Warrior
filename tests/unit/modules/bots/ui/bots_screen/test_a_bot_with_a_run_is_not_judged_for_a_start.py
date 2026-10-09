"""`BOT-174` — a bot that already has a run is not judged for a Start.

@details Owner's evidence (PR #456): a RUNNING mainnet bot with capital 35 had 3 BUYs
locking about 17 USDT and had spent about 17 on its opening buy, so 1.96 USDT was
free, and the Plan showed "Blocks Start: The capital is 35 USDT, above the 1.95
available". The bot's resting orders and held base are its capital, not a shortfall.
The balance rule is a Start's (and a halted bot's Resume's): bots in any other state
get no readiness, no exchange read and no verdict from it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.fenced_reads import (
    ReadKind,
)

from .bots_screen_fixtures import stored
from .connect_screen_helpers import poor_account, select


@pytest.mark.parametrize(
    "state", [S.RUNNING, S.PAUSED, S.STOPPING, S.RECOVERING, S.STARTING]
)
def test_a_bot_with_a_run_and_little_free_quote_shows_no_blocking_verdict(
    open_bots_screen, state: S
) -> None:
    """Its resting orders and held base are its capital, not a shortfall: the free
    quote is below the capital because the bot is spending it (owner's evidence,
    a RUNNING mainnet bot with capital 35 and 1.96 USDT free)."""
    screen = open_bots_screen([stored("a00001", state)])
    poor_account(screen, Decimal("1.96"))
    screen.settle()
    select(screen, "a00001")
    screen.settle()

    panel = screen.view._kind_panel
    assert panel is not None
    assert not [v for v in screen.presenter._selected.detail().verdicts if v.refuses]
    assert panel.field_error_text("capital_quote") == ""
    assert screen.view.model.readiness is None
    assert [a for _, a in screen.pool.pending if a[:1] == (ReadKind.EXCHANGE,)] == []
