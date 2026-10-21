"""`BUG-247` - an unread account read is DEBUG when it met the exchange's pause and ERROR otherwise.

@details Two seams convert a failed read into "unread": `BotAccountReads.position` and the
protective stop's open-stops read (`log_unread_stops`). The pause is told once by the venue's gate;
a failure that is not the pause keeps its ERROR and traceback, so a real fault is never hidden."""

from __future__ import annotations

import logging
from datetime import timedelta
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.unread_streak import (
    UnreadStreak,
    log_unread_stops,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_account_reads import (
    BotAccountReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_identity import (
    BotIdentity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)

_LOGGER = "App.Bots.GridExecutor"
_IDENTITY = BotIdentity("bot.abc123", "abc123", "BTCUSDT")
_PAUSE = ExchangeRateLimitedError(timedelta(seconds=30), banned=False, raw_message="x")


def _reads(failure: Exception) -> BotAccountReads:
    snapshot = FakeAccountSnapshot()
    snapshot.positions_raise(failure)
    ports = Mock()
    ports.account_snapshot = snapshot
    return BotAccountReads(ports, _IDENTITY)


def test_a_position_read_the_pause_refused_is_unread_at_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        assert _reads(_PAUSE).position() is None

    assert [r.levelno for r in caplog.records] == [logging.DEBUG]


def test_a_position_read_that_failed_for_another_reason_is_an_error_with_its_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        assert _reads(RuntimeError("socket closed")).position() is None

    (record,) = caplog.records
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None


def test_an_open_stops_read_the_pause_refused_is_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger(_LOGGER)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        log_unread_stops(logger, _PAUSE, "abc123")

    assert [r.levelno for r in caplog.records] == [logging.DEBUG]


def test_an_open_stops_read_that_failed_for_another_reason_is_an_error_with_its_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger(_LOGGER)
    with caplog.at_level(logging.DEBUG, logger=_LOGGER):
        log_unread_stops(logger, RuntimeError("bad payload"), "abc123")

    (record,) = caplog.records
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None


def test_a_run_of_failed_reads_is_a_warning_once_and_debug_until_a_read_works() -> None:
    streak = UnreadStreak()

    first, second = streak.failed(), streak.failed()
    streak.cleared()

    assert (first, second, streak.failed()) == (
        logging.WARNING,
        logging.DEBUG,
        logging.WARNING,
    )
