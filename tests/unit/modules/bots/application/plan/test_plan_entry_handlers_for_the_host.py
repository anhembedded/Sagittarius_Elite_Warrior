"""`EPIC-045C` - the host's apply-entry and unplan handlers: one entry in, the offline apply's answer out."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.wish_ledger import (
    set_wish,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.apply_plan_entry_for_host import (
    ApplyPlanEntryForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.unplan_bot_for_host import (
    UnplanBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedBot,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ApplyPlanEntryForHostCommand,
    UnplanBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    CommandWorld,
    MemoryAppliedPlanStore,
    StubKind,
    save_bot,
)

S = BotLifecycleState
_OLD = {"lower": "60000", "upper": "70000"}


def _entry(name: str = "fresh", kind: str = "grid", **params: str) -> NewBotEntry:
    chosen = params or _OLD
    return NewBotEntry(
        name,
        kind,
        "spot_testnet",
        "BTCUSDT",
        tuple(ParameterSetting(k, v) for k, v in chosen.items()),
    )


class _Rig:
    def __init__(self) -> None:
        self.world = CommandWorld()
        self.plans = MemoryAppliedPlanStore()
        lock = BotCommandLock()
        self.apply = ApplyPlanEntryForHostCommandHandler(
            self.world, self.plans, BotKindCatalog([StubKind("grid")]), lock
        )
        self.unplan = UnplanBotForHostCommandHandler(self.plans, lock)

    def count(self) -> int:
        return len(self.world.store.load_all().bots)


def test_a_new_entry_becomes_a_draft_with_its_wish_recorded() -> None:
    rig = _Rig()

    result = rig.apply.execute(ApplyPlanEntryForHostCommand(_entry(), "running"))

    assert result.accepted and result.bot_id is not None
    (stored,) = rig.world.store.load_all().bots
    assert stored.bot.state is S.DRAFT
    assert rig.plans.plan is not None
    assert rig.plans.plan.desired_for(result.bot_id) is DesiredState.RUNNING


def test_an_entry_with_an_unknown_kind_is_refused_and_nothing_changes() -> None:
    rig = _Rig()

    result = rig.apply.execute(
        ApplyPlanEntryForHostCommand(_entry(kind="martingale"), "running")
    )

    assert not result.accepted and result.refusal is BotRefusal.INVALID_DEFINITION
    assert rig.count() == 0 and rig.plans.writes == 0


def test_a_secret_like_parameter_name_is_refused_as_a_plan_refuses_it() -> None:
    rig = _Rig()

    result = rig.apply.execute(
        ApplyPlanEntryForHostCommand(_entry(api_secret="x"), "running")
    )

    assert not result.accepted and rig.count() == 0 and rig.plans.writes == 0


def test_a_desired_state_that_is_not_a_wish_is_refused() -> None:
    rig = _Rig()

    result = rig.apply.execute(ApplyPlanEntryForHostCommand(_entry(), "paused"))

    assert not result.accepted and rig.count() == 0 and rig.plans.writes == 0


def test_an_edit_of_a_bot_that_is_running_is_refused_as_needs_stop_first() -> None:
    rig = _Rig()
    save_bot(rig.world.store, "dddddd", S.RUNNING, "busy", _OLD)

    result = rig.apply.execute(
        ApplyPlanEntryForHostCommand(_entry("busy", lower="1", upper="2"), "running")
    )

    assert not result.accepted and result.refusal is BotRefusal.INVALID_TRANSITION
    assert "stop" in result.message
    (stored,) = rig.world.store.load_all().bots
    assert dict(stored.bot.definition.config) == _OLD


def test_an_unplan_removes_the_wish_and_touches_nothing_else() -> None:
    rig = _Rig()
    save_bot(rig.world.store, "dddddd", S.RUNNING, "busy", _OLD)
    set_wish(
        rig.plans,
        AppliedBot("dddddd", "busy", "spot_testnet", DesiredState.RUNNING),
    )

    result = rig.unplan.execute(UnplanBotForHostCommand("dddddd"))

    assert result.accepted
    assert rig.plans.plan is not None and rig.plans.plan.bots == ()
    (stored,) = rig.world.store.load_all().bots
    assert stored.bot.state is S.RUNNING


def test_an_unplan_of_a_bot_with_no_wish_is_answered_without_a_write() -> None:
    rig = _Rig()

    result = rig.unplan.execute(UnplanBotForHostCommand("dddddd"))

    assert result.accepted and "no wish" in result.message
    assert rig.plans.writes == 0
