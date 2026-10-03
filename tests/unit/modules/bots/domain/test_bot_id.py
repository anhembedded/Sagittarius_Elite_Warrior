"""`EPIC-029B` — six characters of `[a-z0-9]`, the order tag of ADR D5."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import (
    BOT_ID_LENGTH,
    BotId,
    BotIdGenerator,
    InvalidBotIdError,
)


@pytest.mark.parametrize("value", ["abc123", "000000", "zzzzzz"])
def test_a_valid_id(value: str) -> None:
    assert str(BotId(value)) == value


@pytest.mark.parametrize(
    "value", ["", "abc12", "abc1234", "ABC123", "abc-12", "abc 12"]
)
def test_an_invalid_id_is_refused(value: str) -> None:
    with pytest.raises(InvalidBotIdError):
        BotId(value)


def test_the_generator_draws_valid_ids_that_differ() -> None:
    generator = BotIdGenerator()
    drawn = {generator.next_id().value for _ in range(200)}
    assert all(len(value) == BOT_ID_LENGTH for value in drawn)
    assert len(drawn) > 190
