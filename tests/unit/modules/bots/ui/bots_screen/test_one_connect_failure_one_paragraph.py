"""`BUG-181` — one Connect failure is one advisory paragraph on screen.

@details The owner's screenshot of the Bots mode, a bot on Spot Testnet whose key the
exchange refuses (`-2015`), held the same sentence ("The exchange does not accept
this API key…") in four places: the message bar, the identity strip, the centre of
the chart area and the Plan's Connect item. `ui-presentation-rule.md` §10 says a
background failure is one bar; the other surfaces carry a short state, not the
advice. This test counts the advice over everything the screen shows, for every
kind of failure a read of the venue's account can have, so a surface that copies
the paragraph again fails here.

Retire when: the Connect step has no failure kind with an advisory sentence.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.connect_failure_words import (
    failure_cause,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)

from .bots_screen_fixtures import BotsScreen, stored
from .connect_screen_helpers import failure, locked_note, select, start_rule


def _bars(screen: BotsScreen) -> list[FailureNotice]:
    """What the message bars say now: one notice per cause, the last told."""
    newest = {notice.cause: notice for notice in screen.notifier.failures}
    return [
        notice
        for cause, notice in newest.items()
        if notice.kind is FailureKind.BACKGROUND
        and cause not in screen.notifier.cleared
    ]


def _every_text_on_screen(screen: BotsScreen) -> list[str]:
    """Every sentence a person can read: the bars' headlines and every label of
    the mode, with Start's reason."""
    labels = [
        label.text() for label in screen.view.findChildren(QLabel) if label.text()
    ]
    return [
        *(bar.headline for bar in _bars(screen)),
        *labels,
        start_rule(screen)[1],
        screen.view.identity.status_label.text(),
    ]


@pytest.mark.parametrize("kind", list(ConnectionFailureKind))
def test_a_refused_connect_tells_its_advice_in_one_bar_and_only_there(
    open_bots_screen, kind: ConnectionFailureKind
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    refusal = failure(kind)
    screen.account.answer_with(refusal)
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    advice = failure_cause(refusal)
    told = [text for text in _every_text_on_screen(screen) if advice in text]
    assert len(told) == 1, told
    assert told == [bar.headline for bar in _bars(screen)]


def test_the_surfaces_that_are_not_the_bar_name_the_state_in_a_few_words(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.account.answer_with(failure(ConnectionFailureKind.KEY_REJECTED))
    screen.settle()

    select(screen, "a00001")
    screen.settle()

    assert locked_note(screen) == "Spot Testnet: Not connected: key refused"
    assert "Not connected" in screen.view.identity.connection.text()
    assert "key refused" in screen.view.identity.connection.text()
    plan = screen.view.plan.readiness_items.text()
    assert "Not connected: key refused" in plan
    assert len(plan) < 120
