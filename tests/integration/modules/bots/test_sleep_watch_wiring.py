"""`EPIC-035I` — `BotsModule.boot()` builds the sleep watch (`CS-002`).

A watch nobody constructs sees no sleep: delete `begin()` from `boot()` and a
laptop can sleep through a stop loss unnoticed. Resolved from the module's real
container, as the other wiring tests are.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.sleep_watch import (
    DEFAULT_SLEEP_LIMITS,
    SleepWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    IFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_retry_scheduler import (
    FakeBotRetryScheduler,
)

from .bots_module_world import registered


def test_boot_arms_the_sleep_watch_heartbeat(tmp_path: Path) -> None:
    module, context = registered(tmp_path)
    retries = FakeBotRetryScheduler()
    context.container.singleton(IBotRetryScheduler, retries)

    module.boot(context)

    owners = [type(r.task.__self__) for r in retries.pending]  # type: ignore[attr-defined]
    assert SleepWatch in owners
    sleep_beat = next(r for r in retries.pending if type(r.task.__self__) is SleepWatch)  # type: ignore[attr-defined]
    assert sleep_beat.delay == DEFAULT_SLEEP_LIMITS.check_every
    module.shutdown(context)
    assert retries.pending == [], "shutdown ends the heartbeat"


def test_the_fresh_price_comes_from_the_venues_own_ports(tmp_path: Path) -> None:
    _module, context = registered(tmp_path)

    reader = context.container.resolve(IFreshPriceReader)

    assert type(reader).__name__ == "VenueFreshPriceReader"
