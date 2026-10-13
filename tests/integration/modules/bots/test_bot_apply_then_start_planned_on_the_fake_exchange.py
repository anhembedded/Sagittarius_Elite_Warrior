"""`EPIC-038I` - a plan file becomes bots, and `run --start-planned` starts the ones it wants running.

The composed app, its real stores and the real Grid kind, over the fake Binance server:
`bot apply` (the `PlanApplier` the verb drives) creates the bots through the commands the
screen dispatches and records the desired states; the host's start step reads that record
(`AppliedBotPlan`, bound by `create_app()`) and starts exactly the bots that want to run.
Nothing reaches a real exchange.
"""

from __future__ import annotations

import json
import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_parser import (
    parse_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_applier import (
    PlanApplier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_plan import IBotPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_steps import (
    StartPlannedBots,
)

from .grid_fake_exchange import (
    GRID,
    SPOT,
    SYMBOL,
    BootedApp,
    FakeExchange,
    booted,
    ladder,
    resting,
)

S = BotLifecycleState


def _plan(*bots: dict[str, object]) -> str:
    return json.dumps({"schema": "sew.bot-plan/1", "bots": list(bots)})


def _bot(name: str, desired: str, **params: str) -> dict[str, object]:
    return {
        "name": name,
        "kind": "grid",
        "venue": SPOT.value,
        "symbol": SYMBOL,
        "params": {**GRID, **params},
        "desired_state": desired,
    }


def _applier(app: BootedApp) -> PlanApplier:
    container = app.engine.container
    return PlanApplier(
        container.resolve(ICommandDispatcher), container.resolve(IAppliedPlanStore)
    )


def _document(app: BootedApp, text: str):  # type: ignore[no-untyped-def]
    return parse_plan(text, app.engine.container.resolve(IBotKindCatalog))


def _ids_by_name(app: BootedApp) -> dict[str, str]:
    listing = app.engine.container.resolve(ICommandDispatcher).dispatch(
        ListBotsQuery, ListBotsQuery()
    )
    return {bot.name: bot.bot_id for bot in listing.bots}  # type: ignore[attr-defined]


def test_apply_creates_the_bots_and_start_planned_starts_only_the_ones_that_want_to_run(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        plan = _document(app, _plan(_bot("runs", "running"), _bot("waits", "stopped")))

        result = _applier(app).apply(plan, PrunePolicy.KEEP)

        assert result.exit_ok
        ids = _ids_by_name(app)
        assert app.bot(ids["runs"]).state is S.DRAFT, "applying starts nothing"
        assert app.bot(ids["waits"]).state is S.DRAFT
        assert (exchange.tmp_path / "bot_plan.json").exists(), (
            "the record, beside the bots"
        )

        host_plan = app.engine.container.resolve(IBotPlan)
        assert host_plan.exists() and host_plan.problem() is None
        assert host_plan.wants_running() == frozenset({ids["runs"]})
        StartPlannedBots(
            host_plan, app.engine.container.resolve(ICommandDispatcher), None
        ).run()

        assert app.bot(ids["runs"]).state is S.RUNNING
        assert resting(app.urls) == ladder(app.runtime(ids["runs"])) != {}
        assert app.bot(ids["waits"]).state is S.DRAFT


def test_a_second_apply_changes_nothing_and_a_bot_is_not_created_twice(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        plan = _document(app, _plan(_bot("runs", "running")))
        _applier(app).apply(plan, PrunePolicy.KEEP)
        record = (exchange.tmp_path / "bot_plan.json").read_bytes()

        second = _applier(app).apply(plan, PrunePolicy.KEEP)

        assert not second.diff.has_changes
        assert len(_ids_by_name(app)) == 1
        assert (exchange.tmp_path / "bot_plan.json").read_bytes() == record


def test_a_running_bots_range_edit_is_refused_by_the_lifecycle_table_on_the_real_app(
    exchange: FakeExchange,
) -> None:
    with booted(exchange) as app:
        _applier(app).apply(
            _document(app, _plan(_bot("runs", "running"))), PrunePolicy.KEEP
        )
        bot_id = _ids_by_name(app)["runs"]
        StartPlannedBots(
            app.engine.container.resolve(IBotPlan),
            app.engine.container.resolve(ICommandDispatcher),
            None,
        ).run()
        assert app.bot(bot_id).state is S.RUNNING

        changed = _document(app, _plan(_bot("runs", "running", lower="47000")))
        result = _applier(app).apply(changed, PrunePolicy.KEEP)

        assert not result.exit_ok
        (outcome,) = result.outcomes
        assert "stop" in outcome.message.lower()
        assert app.bot(bot_id).state is S.RUNNING
        assert dict(app.bot(bot_id).definition.config)["lower"] == GRID["lower"]


class _Records(logging.Handler):
    """`caplog` sees nothing: the composed app turns propagation off, so listen on the logger."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_a_planned_bot_the_kind_refuses_is_not_started_and_the_step_says_so(
    exchange: FakeExchange,
) -> None:
    """The plan holds parameters; whether they are acceptable is the kind's call at start."""
    handler, logger = _Records(), logging.getLogger("App.Operations.Host")
    logger.addHandler(handler)
    try:
        with booted(exchange) as app:
            bad = _bot("bad", "running", lower="52000", upper="48000")
            _applier(app).apply(_document(app, _plan(bad)), PrunePolicy.KEEP)

            StartPlannedBots(
                app.engine.container.resolve(IBotPlan),
                app.engine.container.resolve(ICommandDispatcher),
                None,
            ).run()

            assert app.bot(_ids_by_name(app)["bad"]).state is S.DRAFT
            assert resting(app.urls) == {}
    finally:
        logger.removeHandler(handler)
    assert any(
        "was not started" in r.getMessage() and r.levelno == logging.WARNING
        for r in handler.records
    ), [r.getMessage() for r in handler.records]
