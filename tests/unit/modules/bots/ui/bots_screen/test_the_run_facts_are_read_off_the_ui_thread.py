"""`EPIC-048B` — the Bots screen reads a bot's Run facts on the thread manager, holds them, and
re-judges an edit without asking for them again.

The Run facts are host facts (DERISK §8.1): the other bots are read from the store, the lease
from the trading session. Reading them on the UI thread would stall the screen on a slow store
and, behind a remote backend, on the link. A re-judge after an edit (`REJUDGE_MS`) asks for
nothing: the budget of the edit is judged from the caps the held facts carry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_run_facts import (
    GetBotRunFactsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)

from .bots_screen_fixtures import (
    GOOD_CONFIG,
    SYMBOL,
    BotsScreen,
    ContainerDispatcher,
    HeldPool,
    stored,
)


class _Where:
    """Records, for each Run facts read, whether the pool was running a task."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.in_pool = False
        self.reads: list[bool] = []
        run, dispatch = HeldPool.run, ContainerDispatcher.dispatch
        where = self

        def pooled(pool: HeldPool, index: int) -> None:
            where.in_pool = True
            try:
                run(pool, index)
            finally:
                where.in_pool = False

        def recorded(
            dispatcher: ContainerDispatcher,
            handler_class: type,
            input_dto: object | None = None,
        ) -> Any:
            if handler_class is GetBotRunFactsQuery:
                where.reads.append(where.in_pool)
            return dispatch(dispatcher, handler_class, input_dto)

        monkeypatch.setattr(HeldPool, "run", pooled)
        monkeypatch.setattr(ContainerDispatcher, "dispatch", recorded)


def _start(screen: BotsScreen) -> tuple[bool, str]:
    rule = screen.view.model.availability[BotAction.START]
    return rule.enabled, rule.reason


def test_the_run_facts_are_read_on_the_pool_and_an_edit_reads_none(
    open_bots_screen, monkeypatch: pytest.MonkeyPatch
) -> None:
    where = _Where(monkeypatch)
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()

    screen.view.model.select_requested.emit("a00001")
    screen.settle()

    assert where.reads and all(where.reads)
    assert _start(screen)[0]

    asked = len(where.reads)
    screen.presenter._on_config_edited({**GOOD_CONFIG, "grid_count": "300"})
    screen.presenter._refresh_detail()

    assert len(where.reads) == asked
    assert not _start(screen)[0]


def test_start_waits_for_the_run_facts_once_nothing_else_is_left(
    open_bots_screen,
) -> None:
    """Every other read answered, the Run facts' still held back: Start is not offered."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    pool = screen.pool
    held = [task for task in pool.pending if _is_run_facts_read(task)]
    assert len(held) == 1
    pool.pending = [task for task in pool.pending if task not in held]
    pool.run_all()

    enabled, reason = _start(screen)

    assert not enabled
    assert reason == (
        "1 thing left: Spot Testnet: "
        "Checking the other bots, the symbol's lease and the venue…"
    )

    pool.pending.extend(held)
    pool.run_all()

    assert _start(screen)[0]


def _is_run_facts_read(task: tuple[Any, tuple[Any, ...]]) -> bool:
    """A pooled read is `(FencedReads._read_on_pool, (kind, action_id, label, task))`."""
    _, args = task
    return bool(args) and getattr(args[0], "value", None) == "run"


def test_another_bot_started_on_the_symbol_is_read_again_and_blocks_start(
    open_bots_screen, qtbot
) -> None:
    """The bots read again (a write elsewhere) ask for the Run facts again."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.settle()
    assert _start(screen)[0]

    screen.store.save(stored("b00002", S.RUNNING))
    qtbot.waitUntil(lambda: bool(screen.pool.pending))
    screen.settle()

    enabled, reason = _start(screen)
    assert not enabled
    assert "b00002" in reason


def test_the_clock_reads_the_run_facts_again(open_bots_screen) -> None:
    """A lease taken while the screen looked elsewhere is seen on the next beat."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.settle()
    screen.trading_session.claim_symbol(SYMBOL, "strategy.1")
    assert _start(screen)[0]

    screen.presenter._clock.timeout.emit()
    screen.settle()

    enabled, reason = _start(screen)
    assert not enabled
    assert "strategy.1" in reason


@pytest.mark.parametrize(
    ("instance", "reads_per_beat"),
    [
        (InstanceAccess.unguarded(), 1),
        (InstanceAccess.declined("another copy writes"), 1),
    ],
    ids=["writing-copy", "read-only-copy"],
)
def test_each_beat_asks_for_the_run_facts_once(
    open_bots_screen,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    instance: InstanceAccess,
    reads_per_beat: int,
) -> None:
    """The writing copy's beat asks itself; a read-only copy's beat re-reads the bots, whose
    answer asks. Either way one read per beat, and never none."""
    where = _Where(monkeypatch)
    JsonBotStore(tmp_path).save(stored("a00001", S.DRAFT))
    screen = open_bots_screen(instance=instance)
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.settle()
    before = len(where.reads)

    screen.presenter._clock.timeout.emit()
    screen.settle()

    assert len(where.reads) - before == reads_per_beat
