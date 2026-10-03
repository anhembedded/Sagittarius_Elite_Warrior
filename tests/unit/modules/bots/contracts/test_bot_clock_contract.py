"""`EPIC-029B` — both clocks pass the clock's contract; the fake's helper is verified."""

from __future__ import annotations

from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.system_bot_clock import (
    SystemBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_clock import (
    BotClockContract,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
    FakeBotClock,
)


class TestFakeBotClock(BotClockContract):
    @pytest.fixture
    def impl(self) -> IBotClock:
        return FakeBotClock()


class TestSystemBotClock(BotClockContract):
    @pytest.fixture
    def impl(self) -> IBotClock:
        return SystemBotClock()


def test_advance_moves_the_fake_forward_by_exactly_that_much() -> None:
    clock = FakeBotClock()
    clock.advance(timedelta(seconds=90))
    assert clock.now() == FAKE_CLOCK_START + timedelta(seconds=90)
