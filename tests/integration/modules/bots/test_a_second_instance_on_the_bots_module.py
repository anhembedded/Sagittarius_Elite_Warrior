"""`EPIC-035H` — a read-only copy of the app boots the bots module and touches no bot.

The bots module on its real container with the access of a *second* copy of the
app. Each test fails when its line is removed from the wiring (`testing-rule.md`
§2): the first when `boot()` loses its early return (the restart rule would
rewrite a running bot's file), the others when the store or the runner loses
its read-only decorator.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ReadOnlyInstanceError
from Sagittarius_Elite_Warrior.src.infrastructure.instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_store import (
    sample_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_retry_scheduler import (
    FakeBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotLifecycle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.bots_module_world import (
    GRID_CONFIG,
    registered,
)


def _a_second_instance(tmp_path: Path) -> InstanceAccess:
    first = InstanceAccess.acquire(tmp_path / "lock" / "instance.lock")
    assert first.read_only is False
    return InstanceAccess.acquire(tmp_path / "lock" / "instance.lock")


def _running_bot_on_disk(tmp_path: Path) -> None:
    sampled = sample_bot().bot
    bot = replace(
        sampled,
        definition=replace(sampled.definition, config=GRID_CONFIG),
        lifecycle=BotLifecycle(BotLifecycleState.RUNNING),
    )
    JsonBotStore(tmp_path / "bots").save(StoredBot(bot))


def test_boot_leaves_a_running_bot_of_the_first_instance_as_it_is(
    tmp_path: Path,
) -> None:
    _running_bot_on_disk(tmp_path)
    module, context = registered(tmp_path / "bots", _a_second_instance(tmp_path))
    retries = FakeBotRetryScheduler()
    context.container.singleton(IBotRetryScheduler, retries)

    module.boot(context)

    stored = JsonBotStore(tmp_path / "bots").load(BotId("abc123")).bot
    assert stored.state is BotLifecycleState.RUNNING, "not rewritten to RECOVERING"
    assert context.container.resolve(BotExecutors).all() == ()
    assert context.streams.calls == [], "no price stream was opened"
    assert retries.pending == [], "no heartbeat was armed"
    assert MarketTickEvent.__name__ not in context.event_bus.subscriptions()
    module.shutdown(context)


def test_a_second_instance_saves_no_bot(tmp_path: Path) -> None:
    module, context = registered(tmp_path / "bots", _a_second_instance(tmp_path))
    module.boot(context)

    with pytest.raises(ReadOnlyInstanceError, match="read-only"):
        context.container.resolve(IBotStore).save(sample_bot())

    assert JsonBotStore(tmp_path / "bots").load_all().bots == ()
    module.shutdown(context)


def test_a_second_instance_starts_no_bot(tmp_path: Path) -> None:
    _running_bot_on_disk(tmp_path)
    module, context = registered(tmp_path / "bots", _a_second_instance(tmp_path))
    module.boot(context)

    result = context.container.resolve(IBotRunner).start("abc123")

    assert result.accepted is False
    assert result.refusal is BotRefusal.READ_ONLY_INSTANCE
    assert "read-only" in result.message
    module.shutdown(context)


def test_the_first_instance_boots_as_before(tmp_path: Path) -> None:
    _running_bot_on_disk(tmp_path)
    module, context = registered(tmp_path / "bots")

    module.boot(context)

    stored = JsonBotStore(tmp_path / "bots").load(BotId("abc123")).bot
    assert stored.state is BotLifecycleState.RECOVERING
    module.shutdown(context)
