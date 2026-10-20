"""`BOT-183` - the session another bot's command opened does not put a RECOVERING bot back to work.

@details Opening a venue's order session announces itself on the bus, and a RECOVERING bot used
to reconcile and lay its ladder on any such announcement. Now the announcement names the bot the
opening was for: a RECOVERING bot goes back to work only on its own opening (its Resume), on an
opening whose opener is unknown (`None`), and never on another bot's or a person's (`BOT-197`: a
manual order, a strategy arm). Nothing is placed or cancelled by the bot that waits.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_opener import (
    OpenedByPerson,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.test_grid_reconciler import (
    restored,
)

S = BotLifecycleState
ENABLED = TradingSwitchCause.ENABLED


def test_a_session_opened_for_another_bot_leaves_a_recovering_bot_waiting() -> None:
    world = restored()
    laid = list(world.book.requests)

    world.executor.facts.on_switch(True, ENABLED, "another")

    assert world.state() is S.RECOVERING
    assert world.book.requests == laid


def test_a_session_opened_for_the_bot_itself_reconciles_it() -> None:
    world = restored()

    world.executor.facts.on_switch(True, ENABLED, world.executor.bot_id)

    assert world.state() is S.RUNNING


def test_a_session_opened_by_a_person_leaves_a_recovering_bot_waiting() -> None:
    """`BOT-197`: a manual order or a strategy arm opened it; the owner did not resume the bot."""
    world = restored()
    laid = list(world.book.requests)

    world.executor.facts.on_switch(True, ENABLED, OpenedByPerson.PERSON)

    assert world.state() is S.RECOVERING
    assert world.book.requests == laid


def test_a_session_opened_for_no_known_opener_reconciles_it() -> None:
    world = restored()

    world.executor.facts.on_switch(True, ENABLED, None)

    assert world.state() is S.RUNNING
