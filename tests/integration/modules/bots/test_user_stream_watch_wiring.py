"""`EPIC-035B` — `BotsModule.boot()` builds the user-stream watch (`CS-002`).

A watch nobody constructs hears nothing: delete its `bus.on(...)` from `boot()`
and no reconnect catches a bot up; delete `begin()` and no stream is ever
'down too long'. Resolved from the module's real container, as the other
wiring tests are.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.user_stream_watch import (
    DEFAULT_USER_STREAM_LIMITS,
    UserStreamWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_retry_scheduler import (
    FakeBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
)

from .bots_module_world import registered


def test_boot_subscribes_the_user_stream_watch_and_arms_its_heartbeat(
    tmp_path: Path,
) -> None:
    module, context = registered(tmp_path)
    retries = FakeBotRetryScheduler()
    context.container.singleton(IBotRetryScheduler, retries)

    module.boot(context)

    [handler] = context.event_bus.subscriptions()[UserStreamHealthEvent.__name__]
    assert isinstance(handler.__self__, UserStreamWatch)
    assert [r.delay for r in retries.pending] == [
        DEFAULT_USER_STREAM_LIMITS.check_every
    ]
    module.shutdown(context)
    assert retries.pending == [], "shutdown ends the heartbeat"
