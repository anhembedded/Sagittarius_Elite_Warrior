"""`EPIC-029B` — the Bot aggregate: immutability, timestamps, restart, delete."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
    InvalidBotTransitionError,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

S = BotLifecycleState
E = BotLifecycleEvent
T0 = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def _definition(name: str = "grid one") -> BotDefinition:
    return BotDefinition(
        name=name,
        kind="grid",
        venue=TradingVenue.SPOT_TESTNET,
        symbol="BTCUSDT",
        config={"lower": "60000"},
    )


def _bot(state: S, run_started_at: datetime | None = None) -> Bot:
    return Bot(BotId("abc123"), _definition(), BotLifecycle(state, run_started_at), T0)


def test_a_draft_has_no_run() -> None:
    bot = Bot.draft(BotId("abc123"), _definition(), T0)
    assert bot.state is S.DRAFT
    assert bot.lifecycle.run_started_at is None
    assert bot.created_at == T0


def test_apply_returns_a_new_bot_and_leaves_the_old_one() -> None:
    bot = Bot.draft(BotId("abc123"), _definition(), T0)
    started = bot.apply(E.START, T0)
    assert started.state is S.STARTING
    assert bot.state is S.DRAFT


@pytest.mark.parametrize("origin", [S.DRAFT, S.STOPPED])
def test_start_from_draft_or_stopped_stamps_a_new_run(origin: S) -> None:
    earlier = T0 - timedelta(days=1)
    bot = _bot(origin, run_started_at=earlier)
    assert bot.apply(E.START, T0).lifecycle.run_started_at == T0


def test_the_run_start_survives_halt_resume_and_recovery() -> None:
    """ADR D6 r2: inventory is derived per run, so the instant must not move."""
    bot = _bot(S.DRAFT).apply(E.START, T0)
    later = T0 + timedelta(hours=1)
    for event in (E.LADDER_READY, E.SWITCH_OFF, E.RESUME, E.LADDER_READY):
        bot = bot.apply(event, later)
    bot = bot.restored(later).apply(E.RECONCILE_OK, later).apply(E.STOP, later)
    assert bot.state is S.STOPPING
    assert bot.lifecycle.run_started_at == T0


@pytest.mark.parametrize(
    ("saved", "loaded"),
    [
        (S.RUNNING, S.RECOVERING),
        (S.PAUSED, S.RECOVERING),
        (S.STARTING, S.HALTED),
        (S.STOPPING, S.STOPPING),
        (S.HALTED, S.HALTED),
        (S.DRAFT, S.DRAFT),
        (S.STOPPED, S.STOPPED),
        (S.ERROR, S.ERROR),
    ],
)
def test_restart_follows_d12(saved: S, loaded: S) -> None:
    assert _bot(saved).restored(T0).state is loaded


@pytest.mark.parametrize("before", [S.RUNNING, S.PAUSED])
def test_reconcile_ok_returns_to_the_state_before_the_restart(before: S) -> None:
    recovered = _bot(before).restored(T0).restored(T0).apply(E.SWITCH_OFF, T0)
    assert recovered.lifecycle.recovering_from is before
    assert recovered.apply(E.RECONCILE_OK, T0).state is before


def test_leaving_recovering_forgets_the_prior_state() -> None:
    halted = _bot(S.RUNNING).restored(T0).apply(E.RECONCILE_MISMATCH, T0)
    assert halted.state is S.HALTED
    assert halted.lifecycle.recovering_from is None


def test_reconcile_ok_without_a_prior_state_raises() -> None:
    """A hand-edited file could say RECOVERING with nothing to return to."""
    with pytest.raises(InvalidBotTransitionError):
        _bot(S.RECOVERING).apply(E.RECONCILE_OK, T0)


@pytest.mark.parametrize("origin", [S.DRAFT, S.STOPPED])
def test_edit_replaces_the_definition_and_lands_on_draft(origin: S) -> None:
    edited = _bot(origin).edited(_definition("renamed"), T0)
    assert edited.state is S.DRAFT
    assert edited.definition.name == "renamed"


def test_edit_while_running_raises() -> None:
    with pytest.raises(InvalidBotTransitionError):
        _bot(S.RUNNING).edited(_definition("renamed"), T0)


@pytest.mark.parametrize("state", [S.DRAFT, S.STOPPED])
def test_draft_and_stopped_are_deletable(state: S) -> None:
    _bot(state).require_deletable()


@pytest.mark.parametrize("state", [s for s in S if s not in {S.DRAFT, S.STOPPED}])
def test_delete_from_any_other_state_raises(state: S) -> None:
    with pytest.raises(InvalidBotTransitionError):
        _bot(state).require_deletable()


def test_apply_refuses_delete_because_a_removed_bot_has_no_value() -> None:
    with pytest.raises(InvalidBotTransitionError):
        _bot(S.DRAFT).apply(E.DELETE, T0)


def test_the_definition_config_cannot_be_mutated() -> None:
    config = {"lower": "60000"}
    definition = BotDefinition(
        "n", "grid", TradingVenue.SPOT_TESTNET, "BTCUSDT", config
    )
    config["lower"] = "1"
    assert definition.config["lower"] == "60000"
    with pytest.raises(TypeError):
        definition.config["lower"] = "2"  # type: ignore[index]


@pytest.mark.parametrize(("name", "symbol"), [("  ", "BTCUSDT"), ("n", "")])
def test_a_definition_needs_a_name_and_a_symbol(name: str, symbol: str) -> None:
    with pytest.raises(ValueError, match="needs"):
        BotDefinition(name, "grid", TradingVenue.SPOT_TESTNET, symbol)
