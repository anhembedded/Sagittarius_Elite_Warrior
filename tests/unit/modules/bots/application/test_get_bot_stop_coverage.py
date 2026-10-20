"""`EPIC-038M` (decision O12) - the host's question "does a stop cover this bot's position?" and its safe answers.

The handler decides only what the venue profile and the runner leave to it: Spot has no stop to ask
about, a position venue's answer is the executor's, and whatever cannot be read is never covered.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_stop_coverage import (
    GetBotStopCoverageQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    GetBotStopCoverageQuery,
    StopCoverage,
    StopCoverageReading,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FakeBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_ID = "abc123"
S = StopCoverage


class _Runner(IBotRunner):
    """Answers the coverage it is given, or raises what it is told to; nothing else is used here."""

    def __init__(self, answer: StopCoverageReading | Exception) -> None:
        self._answer = answer
        self.asked: list[str] = []

    def stop_coverage(self, bot_id: str) -> StopCoverageReading:
        self.asked.append(bot_id)
        if isinstance(self._answer, Exception):
            raise self._answer
        return self._answer

    def start(self, bot_id: str) -> BotCommandResult:
        raise NotImplementedError

    def pause(self, bot_id: str) -> None:
        raise NotImplementedError

    def resume(self, bot_id: str) -> BotCommandResult:
        raise NotImplementedError

    def stop(self, bot_id: str, base: ExposureHandling) -> None:
        raise NotImplementedError

    def confirm_resume(self, bot_id: str) -> None:
        raise NotImplementedError

    def withdraw_resume_proposal(self, bot_id: str) -> None:
        raise NotImplementedError

    def has_resume_proposal(self, bot_id: str) -> bool:
        raise NotImplementedError


def _handler(
    venue: TradingVenue, answer: StopCoverageReading | Exception
) -> tuple[GetBotStopCoverageQueryHandler, _Runner]:
    store = FakeBotStore()
    store.save(
        StoredBot(
            Bot(
                BotId(_ID),
                BotDefinition("grid", "grid", venue, "BTCUSDT", {"lower": "1"}),
                BotLifecycle(BotLifecycleState.RUNNING),
                FakeBotClock().now(),
            ),
            {},
        )
    )
    runner = _Runner(answer)
    return GetBotStopCoverageQueryHandler(store, runner), runner


@pytest.mark.parametrize(
    "venue", [TradingVenue.SPOT_MAINNET, TradingVenue.SPOT_TESTNET]
)
def test_a_spot_bot_has_no_stop_to_cover_and_the_exchange_is_not_asked(
    venue: TradingVenue,
) -> None:
    handler, runner = _handler(venue, RuntimeError("must not be asked"))

    answer = handler.execute(GetBotStopCoverageQuery(_ID))

    assert answer.coverage is S.NOT_APPLICABLE
    assert runner.asked == []


@pytest.mark.parametrize(
    "reading",
    [
        StopCoverageReading(S.COVERED, "its protective stop stands on the exchange"),
        StopCoverageReading(S.UNCOVERED, "no protective stop stands over it"),
        StopCoverageReading(
            S.NOTHING_EXPOSED, "it holds no position and rests no ladder"
        ),
        StopCoverageReading(
            S.UNREAD, "whether its protective stop stands could not be read"
        ),
    ],
    ids=["covered", "uncovered", "nothing_exposed", "unread"],
)
def test_a_futures_bot_answers_what_its_executor_read(
    reading: StopCoverageReading,
) -> None:
    handler, runner = _handler(TradingVenue.FUTURES_MAINNET, reading)

    answer = handler.execute(GetBotStopCoverageQuery(_ID))

    assert (answer.coverage, answer.words) == (reading.coverage, reading.words)
    assert runner.asked == [_ID]


def test_a_read_that_fails_is_unread_never_covered() -> None:
    handler, _ = _handler(TradingVenue.FUTURES_MAINNET, ConnectionError("down"))

    answer = handler.execute(GetBotStopCoverageQuery(_ID))

    assert answer.coverage is S.UNREAD
    assert not answer.coverage.leaves_standing
    assert "ConnectionError" in answer.words


def test_a_position_venue_whose_bot_has_no_protection_is_not_covered() -> None:
    """The Spot answer must never reach a position venue: nothing stands over the position."""
    handler, _ = _handler(
        TradingVenue.FUTURES_MAINNET, StopCoverageReading(S.NOT_APPLICABLE)
    )

    answer = handler.execute(GetBotStopCoverageQuery(_ID))

    assert answer.coverage is S.UNCOVERED


def test_a_bot_whose_record_cannot_be_read_is_unread() -> None:
    handler, runner = _handler(
        TradingVenue.FUTURES_MAINNET, StopCoverageReading(S.COVERED)
    )

    answer = handler.execute(GetBotStopCoverageQuery("nosuch"))

    assert answer.coverage is S.UNREAD and runner.asked == []


def test_only_a_stop_that_covers_or_a_bot_with_nothing_exposed_may_be_left() -> None:
    assert {c for c in S if c.leaves_standing} == {
        S.NOT_APPLICABLE,
        S.NOTHING_EXPOSED,
        S.COVERED,
    }
