"""`EPIC-045G` - the arm refusals' words are one table the screen and the host read, and it is complete."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.strategy.strategy_arm_words import (
    ARM_BLOCK_WORDS,
    DISARM_BLOCKED_WORDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.arm_block_messages import (
    ARM_BLOCK_MESSAGES,
    DISARM_BLOCKED_MESSAGE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyBlockReason,
)


def test_every_reason_has_a_line_the_host_can_read() -> None:
    assert set(ARM_BLOCK_WORDS) == set(ArmStrategyBlockReason)
    assert all(line.strip() for line in ARM_BLOCK_WORDS.values())


def test_the_screen_speaks_the_same_words_as_the_host() -> None:
    for reason in ArmStrategyBlockReason:
        assert ARM_BLOCK_MESSAGES[reason] == ARM_BLOCK_WORDS[reason]
    assert DISARM_BLOCKED_MESSAGE == DISARM_BLOCKED_WORDS
