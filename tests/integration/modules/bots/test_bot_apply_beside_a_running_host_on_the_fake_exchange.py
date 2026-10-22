"""`EPIC-045C` - `bot apply` beside a running host changes real bots, entry by entry, and the record follows.

The composed app over the fake exchange. The operator's `IHostControl` writes command files into the real
directory and the host's own `HostedControlPoller` runs them, so what is proven is the wiring the unit tests
cannot: `apply-entry`, `unplan` and `delete` are bound in the composition root and the executor reaches them.
One mixed plan: a create, an edit of a stopped bot, an edit of a running bot (refused: needs stop first), a
leave, and a prune of a bot at rest. A RUNNING bot beside them keeps its orders.
"""

from __future__ import annotations

import json

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_parser import (
    parse_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_applier import (
    PlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_change import (
    ChangeAction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.cli.bot_plan_host_apply import (
    HostPlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)

from .grid_fake_exchange import GRID, SPOT, SYMBOL, FakeExchange, booted, resting
from .host_control_world import Operator, ids_of, operator_of, state_of

S = BotLifecycleState


class _ThroughTheOperator(IHostControl):
    """The verb's `IHostControl`, answered by the composed host's command directory."""

    def __init__(self, operator: Operator) -> None:
        self._operator = operator
        self.sent: list[HostControlRequest] = []

    def send(self, request: HostControlRequest, wait_s: float) -> HostControlReply:
        self.sent.append(request)
        return self._operator.ask(request)


def _entry(name: str, desired: str, **params: str) -> dict[str, object]:
    return {
        "name": name,
        "kind": "grid",
        "venue": SPOT.value,
        "symbol": SYMBOL,
        "params": {**GRID, **params},
        "desired_state": desired,
    }


def _created(app, name: str) -> str:  # type: ignore[no-untyped-def]
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand(name, "grid", SPOT, SYMBOL, dict(GRID))
    )
    assert isinstance(created, BotCommandResult) and created.bot_id is not None
    return created.bot_id


def _ask(operator: Operator, action: HostControlAction, bot_id: str) -> None:
    reply = operator.ask(HostControlRequest(action, bot_id))
    assert reply.status is HostControlStatus.DONE, reply.message


def test_a_mixed_plan_is_carried_out_beside_a_running_host_and_the_record_follows(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)
        container = app.engine.container
        plans = container.resolve(IAppliedPlanStore)
        edits, retired, busy = (_created(app, n) for n in ("edits", "retired", "busy"))
        _ask(operator, HostControlAction.START, edits)
        _ask(operator, HostControlAction.STOP, edits)
        _ask(operator, HostControlAction.START, busy)
        assert state_of(app.store, edits) is S.STOPPED
        assert state_of(app.store, busy) is S.RUNNING
        orders_before = dict(resting(app.urls))
        assert orders_before
        plan = parse_plan(
            json.dumps(
                {
                    "schema": "sew.bot-plan/1",
                    "bots": [
                        _entry("fresh", "running"),
                        _entry("edits", "running", lower="47000"),
                        _entry("busy", "running", lower="47000"),
                    ],
                }
            ),
            container.resolve(IBotKindCatalog),
        )
        host = _ThroughTheOperator(operator)
        applier = HostPlanApplier(
            PlanApplier(container.resolve(ICommandDispatcher), plans), host, plans
        )

        run = applier.run(plan, PrunePolicy.PRUNE, 15.0)

        assert run.result is not None and run.unsent == 0 and not run.problems
        by_name = {o.change.name: o for o in run.result.outcomes}
        assert {n: (o.change.action, o.done) for n, o in by_name.items()} == {
            "fresh": (ChangeAction.CREATE, True),
            "edits": (ChangeAction.EDIT, True),
            "busy": (ChangeAction.BLOCKED, False),
            "retired": (ChangeAction.DELETE, True),
        }
        assert "stop" in by_name["busy"].message
        assert [r.action for r in host.sent] == [
            HostControlAction.APPLY_ENTRY,
            HostControlAction.APPLY_ENTRY,
            HostControlAction.DELETE,
        ], "the blocked entry is not sent, the delete is last"
        assert retired not in ids_of(app.store)
        assert state_of(app.store, edits) is S.DRAFT, "an edit lands the bot on DRAFT"
        assert app.store.load(BotId(edits)).bot.definition.config["lower"] == "47000"
        assert (
            app.store.load(BotId(busy)).bot.definition.config["lower"] == GRID["lower"]
        )
        assert state_of(app.store, busy) is S.RUNNING
        assert dict(resting(app.urls)) == orders_before, (
            "applying places and cancels no order"
        )
        (fresh,) = ids_of(app.store) - {edits, busy}
        assert state_of(app.store, fresh) is S.DRAFT, "applying starts nothing"
        record = plans.read()
        assert record is not None
        assert {r.name: (r.bot_id, r.desired_state) for r in record.bots} == {
            "fresh": (fresh, DesiredState.RUNNING),
            "edits": (edits, DesiredState.RUNNING),
        }, "busy is blocked so it has no wish; retired is gone"
