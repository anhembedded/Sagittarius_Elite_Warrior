"""`EPIC-040C` — the Backtest tab's sandbox as the Bots selection moves: another bot re-copies from
its saved plan, unless the person has edited the sandbox, in which case the tab asks first."""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_run_facts import (
    BotRunFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest.sandbox_session import (
    SandboxFollow,
    SandboxSession,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.selected_bot import (
    SelectedBot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .sandbox_fixtures import SAVED, bot


def _edited(session: SandboxSession) -> None:
    assert session.plan is not None
    session.edit(session.plan.with_config({**SAVED, "upper": "72000"}))


def test_the_first_selection_copies_the_saved_plan() -> None:
    session = SandboxSession()

    assert session.follow(bot("a3f9c1")) is SandboxFollow.COPIED
    assert session.plan is not None and session.plan.source_bot_id == "a3f9c1"


def test_the_same_saved_plan_arriving_again_changes_nothing() -> None:
    """The screen re-follows the selection on its clock and every planner answer."""
    session = SandboxSession()
    session.follow(bot("a3f9c1"))
    _edited(session)
    before = session.plan

    assert session.follow(bot("a3f9c1")) is SandboxFollow.UNCHANGED
    assert session.plan is before and session.pending_copy is None


def test_another_bot_recopies_when_the_sandbox_is_untouched() -> None:
    session = SandboxSession()
    session.follow(bot("a3f9c1"))

    assert (
        session.follow(bot("b7e2d4", {**SAVED, "grid_count": "6"}))
        is SandboxFollow.COPIED
    )
    assert session.plan is not None
    assert session.plan.source_bot_id == "b7e2d4"
    assert session.plan.config["grid_count"] == "6"


def test_another_bot_asks_before_discarding_edits_and_keeps_them_meanwhile() -> None:
    session = SandboxSession()
    session.follow(bot("a3f9c1"))
    _edited(session)
    edits = session.plan

    assert session.follow(bot("b7e2d4")) is SandboxFollow.NEEDS_CONFIRMATION

    assert session.plan is edits  # nothing is discarded until the person says so
    assert (
        session.pending_copy is not None
        and session.pending_copy.source_bot_id == "b7e2d4"
    )


def test_confirming_replaces_the_edits_with_the_other_bots_plan() -> None:
    session = SandboxSession()
    session.follow(bot("a3f9c1"))
    _edited(session)
    session.follow(bot("b7e2d4"))

    session.confirm_switch()

    assert session.plan is not None and session.plan.source_bot_id == "b7e2d4"
    assert not session.plan.edited and session.pending_copy is None


def test_keeping_the_edits_drops_the_other_bots_copy() -> None:
    session = SandboxSession()
    session.follow(bot("a3f9c1"))
    _edited(session)
    edits = session.plan
    session.follow(bot("b7e2d4"))

    session.keep_current()

    assert session.plan is edits and session.pending_copy is None


def test_the_same_bot_saved_with_a_new_plan_is_a_new_source() -> None:
    session = SandboxSession()
    session.follow(bot("a3f9c1"))

    assert (
        session.follow(bot("a3f9c1", {**SAVED, "upper": "75000"}))
        is SandboxFollow.COPIED
    )
    assert session.plan is not None and session.plan.config["upper"] == "75000"


def test_no_selection_keeps_the_sandbox() -> None:
    session = SandboxSession()
    session.follow(bot())
    _edited(session)
    edits = session.plan

    assert session.follow(None) is SandboxFollow.UNCHANGED
    assert session.plan is edits


def test_reset_restores_the_copy_the_sandbox_was_made_from() -> None:
    session = SandboxSession()
    session.follow(bot())
    _edited(session)

    session.reset()

    assert session.plan is not None and not session.plan.edited


def _selection(snapshot):  # type: ignore[no-untyped-def]
    return SelectedBot(
        BotKindCatalog(()),
        lambda: datetime(2026, 10, 20, tzinfo=UTC),
        BotRunFactsReader(
            FakeVenueTradingPorts(fake_venue_ports(TradingVenue.SPOT_TESTNET)),
            DEFAULT_OWNER_BUDGET_CAPS,
        ),
    )


def test_the_sandbox_copies_the_saved_plan_not_the_plan_panels_unsaved_edits(
    qtbot,
) -> None:  # type: ignore[no-untyped-def]
    """A "what if" must start from what the bot is, not from what is half-typed in its Plan panel,
    and trying one must leave the live edits as they were."""
    saved = bot()
    selected = _selection(saved)
    selected.select(saved)
    selected.edit({**SAVED, "upper": "99999"})  # typed in the live panel, never saved
    session = SandboxSession()

    session.follow(selected.bot)
    assert session.plan is not None
    session.edit(session.plan.with_config({**SAVED, "grid_count": "6"}))
    session.reset()

    assert session.plan.config["upper"] == SAVED["upper"]
    assert dict(selected.edited or {}) == {**SAVED, "upper": "99999"}
    assert dict(selected.bot.config) == SAVED  # type: ignore[union-attr]


def test_keeping_the_edits_is_remembered_for_the_next_refresh_of_the_same_selection() -> (
    None
):
    """The screen re-follows on its clock; a declined question is not asked again."""
    session = SandboxSession()
    session.follow(bot("a3f9c1"))
    _edited(session)
    session.follow(bot("b7e2d4"))
    session.keep_current()

    assert session.follow(bot("b7e2d4")) is SandboxFollow.UNCHANGED
    assert session.follow(bot("b7e2d4")) is SandboxFollow.UNCHANGED
    assert session.pending_copy is None


def test_the_question_is_asked_once_while_it_is_open() -> None:
    session = SandboxSession()
    session.follow(bot("a3f9c1"))
    _edited(session)

    assert session.follow(bot("b7e2d4")) is SandboxFollow.NEEDS_CONFIRMATION
    assert session.follow(bot("b7e2d4")) is SandboxFollow.UNCHANGED
    assert session.pending_copy is not None


def test_a_declined_bot_saved_with_a_new_plan_is_asked_about_again() -> None:
    session = SandboxSession()
    session.follow(bot("a3f9c1"))
    _edited(session)
    session.follow(bot("b7e2d4"))
    session.keep_current()

    changed = bot("b7e2d4", {**SAVED, "upper": "75000"})

    assert session.follow(changed) is SandboxFollow.NEEDS_CONFIRMATION


def test_the_source_saved_anew_while_edited_asks_once() -> None:
    session = SandboxSession()
    session.follow(bot("a3f9c1"))
    _edited(session)
    saved_anew = bot("a3f9c1", {**SAVED, "upper": "75000"})

    assert session.follow(saved_anew) is SandboxFollow.NEEDS_CONFIRMATION
    assert session.follow(saved_anew) is SandboxFollow.UNCHANGED


def test_going_back_to_the_source_while_asking_closes_the_question() -> None:
    session = SandboxSession()
    session.follow(bot("a3f9c1"))
    _edited(session)
    session.follow(bot("b7e2d4"))

    assert session.follow(bot("a3f9c1")) is SandboxFollow.UNCHANGED

    assert session.pending_copy is None
    assert session.plan is not None and session.plan.source_bot_id == "a3f9c1"


def test_a_reset_while_a_question_is_open_lets_the_next_selection_copy() -> None:
    session = SandboxSession()
    session.follow(bot("a3f9c1"))
    _edited(session)
    session.follow(bot("b7e2d4"))
    session.keep_current()

    session.reset()

    assert session.follow(bot("b7e2d4")) is SandboxFollow.COPIED
    assert session.plan is not None and session.plan.source_bot_id == "b7e2d4"


def test_a_bot_moved_to_another_venue_is_a_new_source() -> None:
    """`change_bot_venue` keeps the bot's id and config."""
    session = SandboxSession()
    session.follow(bot("a3f9c1"))

    moved = bot("a3f9c1", venue=TradingVenue.SPOT_MAINNET)

    assert session.follow(moved) is SandboxFollow.COPIED
    assert session.plan is not None and session.plan.venue is TradingVenue.SPOT_MAINNET
