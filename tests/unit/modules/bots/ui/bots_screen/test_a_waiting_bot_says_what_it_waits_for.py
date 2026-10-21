"""`EPIC-044C` — the Plan says what a bot in AWAITING_RANGE waits for, and for which price.

ADR 044 D10: "Waiting for the price to enter X-Y (now Z)". The sentence is the banner's, an
information (not a warning: a wait is what the owner asked for), and the state line keeps the
state word alone so the two do not say the same thing twice.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    bot_facts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_table_models import (
    BotsTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_status import (
    StatusInputs,
    plan_status,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.notice_bar import NoticeKind

from .bots_screen_fixtures import NOW, stored

_WAITING = BotProgress(
    realised_profit=Decimal(0),
    completed_cycles=0,
    open_orders=0,
    inventory=Decimal(0),
    average_cost=None,
    reason="",
    reason_detail="",
    mark_price=Decimal(58000),
)


def _waiting(progress: BotProgress | None = _WAITING) -> BotSnapshot:
    return BotSnapshot.of(stored("a00001", S.AWAITING_RANGE).bot, progress)


def test_the_note_names_the_range_and_the_price_it_waits_on() -> None:
    facts = bot_facts(_waiting(), NOW)

    assert facts.note == (
        "Waiting for the price to enter 60,000.00–70,000.00 (now 58,000.00); "
        "nothing is placed until it does"
    )


def test_the_note_follows_the_price_the_bot_last_heard() -> None:
    above = replace(_WAITING, mark_price=Decimal(71500))

    assert "(now 71,500.00)" in bot_facts(_waiting(above), NOW).note


def test_before_any_price_the_note_says_none_was_heard() -> None:
    note = bot_facts(_waiting(None), NOW).note

    assert "(no price heard yet)" in note
    assert "60,000.00–70,000.00" in note


def test_the_state_line_is_the_state_word_alone() -> None:
    facts = bot_facts(_waiting(), NOW)

    assert facts.state == "Waiting for the range"
    assert facts.state_word == "Waiting for the range"


@pytest.mark.parametrize("state", [s for s in S if s is not S.AWAITING_RANGE])
def test_no_other_state_says_it_waits_for_the_range(state: S) -> None:
    snapshot = BotSnapshot.of(stored("a00002", state).bot, _WAITING)

    assert "enter" not in bot_facts(snapshot, NOW).note


def test_the_banner_shows_the_note_as_information_not_a_warning() -> None:
    facts = bot_facts(_waiting(), NOW)

    status = plan_status(
        StatusInputs(
            state=S.AWAITING_RANGE,
            note=facts.note,
            readiness=None,
            readiness_state=ReadinessState.READY,
            label_of=lambda _key: "",
        )
    )

    assert status.kind is NoticeKind.INFORMATION
    assert status.text == facts.note


def test_the_bots_table_shows_the_state_word_and_does_not_flag_the_wait_for_attention(
    qtbot,
) -> None:
    model = BotsTableModel()
    model.set_rows([_waiting()])
    state = [spec.key for spec in BotsTableModel.COLUMNS].index("state")

    cell = model.index(0, state)

    assert cell.data(Qt.ItemDataRole.DisplayRole) == "Waiting for the range"
    font = cell.data(Qt.ItemDataRole.FontRole)
    assert font is None or not font.bold()
