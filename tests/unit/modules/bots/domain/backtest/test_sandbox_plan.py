"""`EPIC-040C` — a sandbox is a copy of a bot's saved plan: edits change only the copy, Reset
restores the source, and it says which parameters differ."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.backtest.sandbox_fixtures import (
    SAVED,
    bot,
)


def test_a_sandbox_starts_from_the_saved_plan_and_names_its_source() -> None:
    saved = bot("a3f9c1")

    plan = SandboxPlan.from_bot(saved)

    assert dict(plan.config) == SAVED and dict(plan.source_config) == SAVED
    assert (plan.kind_id, plan.venue, plan.symbol, plan.source_bot_id) == (
        saved.kind,
        saved.venue,
        saved.symbol,
        "a3f9c1",
    )
    assert plan.changed_fields() == () and not plan.edited


def test_an_edit_changes_only_the_sandbox_and_is_named() -> None:
    saved = bot()
    plan = SandboxPlan.from_bot(saved)

    edited = plan.with_config({**SAVED, "upper": "72000", "grid_count": "12"})

    assert edited.changed_fields() == ("grid_count", "upper")
    assert edited.edited
    assert dict(saved.config) == SAVED  # the bot's plan is not touched
    assert dict(plan.config) == SAVED  # nor the earlier sandbox: the value is frozen


def test_a_parameter_added_or_removed_counts_as_changed() -> None:
    plan = SandboxPlan.from_bot(bot())

    added = plan.with_config({**SAVED, "leverage": "3"})
    removed = plan.with_config({k: v for k, v in SAVED.items() if k != "stop_loss"})

    assert added.changed_fields() == ("leverage",)
    assert removed.changed_fields() == ("stop_loss",)


def test_reset_restores_the_source_and_leaves_nothing_changed() -> None:
    edited = SandboxPlan.from_bot(bot()).with_config({**SAVED, "upper": "72000"})

    restored = edited.reset()

    assert dict(restored.config) == SAVED
    assert restored.changed_fields() == ()


def test_the_parameters_cannot_be_changed_in_place() -> None:
    plan = SandboxPlan.from_bot(bot())

    with pytest.raises(TypeError):
        plan.config["upper"] = "1"  # type: ignore[index]
