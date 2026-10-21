"""`EPIC-043C`: a bot's state is a word, an icon and a tone; the word is complete and readable."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_state_looks import (
    STATE_LOOKS,
    STATE_WORDS,
    state_look,
    state_text,
    state_tone,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets.asset_validator_extension import (
    REQUIRED_UI_ICONS,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone


@pytest.mark.parametrize("state", list(S), ids=lambda s: s.name)
def test_every_state_has_a_word_a_person_can_read(state: S) -> None:
    word = state_text(state)

    assert word and "_" not in word and word[0].isupper()


def test_awaiting_recovery_is_two_words_not_a_variable_name() -> None:
    assert state_text(S.AWAITING_RECOVERY) == "Awaiting recovery"
    assert state_text(S.HALTED) == "Halted"


def test_the_words_table_is_complete_for_every_member() -> None:
    assert set(STATE_WORDS) == set(S)


@pytest.mark.parametrize(
    ("state", "icon", "tone"),
    [
        (S.RUNNING, "play", Tone.POSITIVE),
        (S.PAUSED, "pause", Tone.CAUTION),
        (S.RECOVERING, "rotate-ccw", Tone.CAUTION),
        (S.AWAITING_RECOVERY, "rotate-ccw", Tone.CAUTION),
        (S.HALTED, "triangle-alert", Tone.NEGATIVE),
        (S.ERROR, "triangle-alert", Tone.NEGATIVE),
    ],
)
def test_the_states_that_need_a_look_have_the_one_the_owner_asked_for(
    state: S, icon: str, tone: Tone
) -> None:
    look = state_look(state)

    assert look is not None
    assert (look.icon, look.tone) == (icon, tone)
    assert state_tone(state) is tone


def test_a_draft_has_no_icon_and_no_tone() -> None:
    assert state_look(S.DRAFT) is None
    assert state_tone(S.DRAFT) is Tone.NEUTRAL


def test_every_icon_a_state_uses_is_one_the_application_requires() -> None:
    """A missing file would show a blank where the icon should be."""
    assert {look.icon for look in STATE_LOOKS.values()} <= set(REQUIRED_UI_ICONS)
