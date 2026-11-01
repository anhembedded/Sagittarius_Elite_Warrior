"""`EPIC-047E` (AC2) - what the host writes for a bot reaches the tab's picture, and the tab redraws, inside five seconds.

The business promise: a fill on the VPS appears in the tab in at most 5 s. A fill is a write of the bot's file (its progress
and orders); this measures that write against the tab's picture over the real bridge session, and adds the tab's own
redraw pacing to it, so the sum is held to the budget by a test rather than by a comment. The owner's measurement with
real fills on the VPS (the fill's own timestamp against the screen) is the owner step marked pending in the task.
"""

from __future__ import annotations

import time
from dataclasses import replace
from decimal import Decimal
from typing import Final

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.presenter_pacing import (
    COALESCE_MS,
)
from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import POLL_S
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import VpsTabWorld
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    full_bot,
)

BUDGET_S: Final = 5.0


def test_a_write_of_a_bot_on_the_host_reaches_the_picture_within_the_budget(
    tab: VpsTabWorld,
) -> None:
    bot = full_bot()
    assert bot.progress is not None
    filled = replace(
        bot, progress=replace(bot.progress, realised_profit=Decimal("123.45"))
    )

    wrote = time.monotonic()
    tab.host.bots.put(filled)
    tab.wait_bot_changed()
    seen = time.monotonic() - wrote

    held = {b.bot_id: b for b in tab.world.current().bots}[bot.bot_id]
    assert isinstance(held.progress, BotProgress)
    assert held.progress.realised_profit == Decimal("123.45")
    assert seen + COALESCE_MS / 1000 < BUDGET_S


def test_the_pacing_the_tab_adds_leaves_most_of_the_budget_to_the_host_and_the_network() -> (
    None
):
    """The bridge looks at the bot files every POLL_S and the screen coalesces re-reads for COALESCE_MS: together under
    a tenth of the budget, so the rest is the host's write and the SSH round trip."""
    assert POLL_S + COALESCE_MS / 1000 < BUDGET_S / 10
