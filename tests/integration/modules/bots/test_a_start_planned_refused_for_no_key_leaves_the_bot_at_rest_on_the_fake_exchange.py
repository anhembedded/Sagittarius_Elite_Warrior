"""`BUG-223` - a planned start the readiness refuses leaves the bot at rest, on disk and across a boot.

The host's `--start-planned` dispatches the screen's Start. On a venue with no key the
readiness refuses (`VENUE_NOT_READY`) before anything is saved, so the bot keeps the state it
had: the next boot does not turn it RECOVERING, and the next `--start-planned` and the plan
diff still see a bot at rest. This pins that promise on the composed app and the real stores.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_steps import (
    StartPlannedBots,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
)

from .grid_fake_exchange import FakeExchange, booted
from .test_the_run_hosts_start_up_steps_on_the_fake_exchange import (
    _created,
    _dispatcher,
    _Plan,
)

S = BotLifecycleState


def test_a_refused_planned_start_leaves_the_bot_at_rest_across_the_next_boot(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(SPOT_ENV_API_KEY)
    monkeypatch.delenv(SPOT_ENV_API_SECRET)
    with booted(exchange) as first:
        bot_id = _created(first)

        StartPlannedBots(_Plan(bot_id), _dispatcher(first), None).run()

        assert first.bot(bot_id).state is S.DRAFT

    with booted(exchange) as second:
        assert second.bot(bot_id).state is S.DRAFT
