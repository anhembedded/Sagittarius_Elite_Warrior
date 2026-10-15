"""`BUG-222` - a restored bot's boot report on a venue with no API key is a sentence, not an error.

A host with no key for a venue (the CLI `bot apply`, a unit started before its key was
saved) still boots the bots module, whose restart rule makes a RUNNING bot RECOVERING and
whose boot recovery reads the exchange once to count the bot's orders. With no key there
is nothing to read: the report says so on the bot, and the log holds no ERROR and no
traceback for a state the operator can fix by saving a key.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
)

from .grid_fake_exchange import FakeExchange, booted
from .test_the_run_hosts_start_up_steps_on_the_fake_exchange import _created

S = BotLifecycleState


def test_a_recovering_bot_on_a_venue_with_no_key_reports_it_without_an_error(
    exchange: FakeExchange,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with booted(exchange) as first:
        bot_id = _created(first)
        first.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
        assert first.bot(bot_id).state is S.RUNNING

    monkeypatch.delenv(SPOT_ENV_API_KEY)
    monkeypatch.delenv(SPOT_ENV_API_SECRET)
    with (
        caplog.at_level(logging.DEBUG),
        booted(exchange, open_session=False) as second,
    ):
        assert second.bot(bot_id).state is S.RECOVERING
        runtime = second.runtime(bot_id)

    assert runtime.reason is GridReason.RECOVERY_READ
    assert "no API key" in runtime.reason_detail
    loud = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert [r.getMessage() for r in loud] == []
    assert [r for r in loud if r.exc_info] == []
