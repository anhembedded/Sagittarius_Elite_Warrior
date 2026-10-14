"""`BOT-179` - the plan export is common to every bot kind.

A bot of a kind the plan code has never heard of, with a config of its own shape, goes
through the real query and the real writer; the parser knows the kind only from the
catalog, and the file applies as "no changes". Nothing here names the Grid.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.plan_file import (
    PlanFileWritten,
    write_new_plan_file,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_parser import (
    InvalidBotPlanError,
    parse_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_differ import (
    PrunePolicy,
    diff_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    ExportBotPlanQuery,
    ExportBotPlanQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
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

_KIND = "second_kind"
_CONFIG = {"rungs": "7", "spacing_bps": "35", "note": "opaque to the plan code"}


def _world() -> CommandWorld:
    world = CommandWorld()
    save_bot(
        world.store, "aaaaaa", BotLifecycleState.RUNNING, "first", _CONFIG, kind=_KIND
    )
    save_bot(
        world.store, "bbbbbb", BotLifecycleState.STOPPED, "second", _CONFIG, kind=_KIND
    )
    return world


def test_a_second_kind_exports_through_the_real_query_and_writer_and_applies_as_no_changes(
    tmp_path: Path,
) -> None:
    world = _world()
    document = ExportBotPlanQueryHandler(world, MemoryAppliedPlanStore()).execute(
        ExportBotPlanQuery()
    )

    written = write_new_plan_file(tmp_path / "plan.json", document.to_json_text())
    assert isinstance(written, PlanFileWritten)
    reread = parse_plan(
        written.path.read_text(encoding="utf-8"), BotKindCatalog([StubKind(_KIND)])
    )
    listing = world.dispatch(ListBotsQuery, ListBotsQuery()).bots  # type: ignore[attr-defined]
    diff = diff_plan(reread, listing, None, PrunePolicy.PRUNE)

    assert {bot.kind for bot in reread.bots} == {_KIND}
    assert all(dict(bot.params) == _CONFIG for bot in reread.bots), (
        "config is carried verbatim"
    )
    assert not diff.has_changes, [c.detail for c in diff.changes]


def test_the_catalog_decides_which_kinds_a_plan_may_name() -> None:
    document = ExportBotPlanQueryHandler(_world(), MemoryAppliedPlanStore()).execute(
        ExportBotPlanQuery()
    )

    with pytest.raises(InvalidBotPlanError, match="not a kind of bot here"):
        parse_plan(document.to_json_text(), BotKindCatalog([StubKind("another_kind")]))
