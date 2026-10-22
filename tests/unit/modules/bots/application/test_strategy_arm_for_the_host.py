"""`EPIC-045G` - the host's arm and disarm are the Bots tab's Arm strategy and Disarm strategy.

They add no way to arm: they ask the venue's own `IStrategyArmingControl`, with the saved arming, and speak
the tab's words. What they add: no parameter typed on a command line, a mainnet arm only with the typed venue,
and one refusal the tab makes by greying a command out (a venue that already has a strategy armed).
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import STRATEGY_SUBJECT
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.arm_strategy_for_host import (
    ArmStrategyForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.disarm_strategy_for_host import (
    DisarmStrategyForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ArmStrategyForHostCommand,
    DisarmStrategyForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyBlockReason,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .strategy_controls_world import SAVED, MemoryControls, refused

TESTNET = TradingVenue.SPOT_TESTNET
MAINNET = TradingVenue.SPOT_MAINNET


def _arm(controls: MemoryControls, venue: str, typed: str | None = None):
    return ArmStrategyForHostCommandHandler(controls).execute(
        ArmStrategyForHostCommand(venue, typed)
    )


def test_arming_a_testnet_venue_arms_the_saved_arming_and_names_it() -> None:
    controls = MemoryControls(TESTNET)

    result = _arm(controls, "spot_testnet")

    assert result.accepted and result.bot_id == STRATEGY_SUBJECT
    assert controls.arming[TESTNET].arm_calls == [SAVED], (
        "exactly the saved arming, nothing typed"
    )
    for word in ("ema_crossover", "BTCUSDT", "5m", "fast=9", "slow=21", "spot_testnet"):
        assert word in result.message


def test_a_mainnet_arm_is_not_dispatched_until_the_venue_is_typed() -> None:
    controls = MemoryControls(MAINNET)

    untyped = _arm(controls, "spot_mainnet")
    wrong = _arm(controls, "spot_mainnet", "spot_testnet")

    assert untyped.refusal is wrong.refusal is BotRefusal.REAL_MONEY_NOT_CONFIRMED
    assert "--confirm-venue spot_mainnet" in untyped.message
    assert controls.arming[MAINNET].arm_calls == [], (
        "nothing armed: a strategy would trade real money"
    )


def test_a_mainnet_arm_with_its_venue_typed_arms() -> None:
    controls = MemoryControls(MAINNET)

    assert _arm(controls, "spot_mainnet", "spot_mainnet").accepted
    assert controls.arming[MAINNET].armed == SAVED


def test_a_testnet_arm_needs_no_typed_venue_but_a_wrong_one_is_ignored_harmlessly() -> (
    None
):
    controls = MemoryControls(TESTNET)

    assert _arm(controls, "spot_testnet", "spot_mainnet").accepted


@pytest.mark.parametrize("text", ["", "SPOT", "nowhere", "disabled"])
def test_a_venue_this_build_does_not_have_is_refused_in_words(text: str) -> None:
    controls = MemoryControls(TESTNET)

    result = _arm(controls, text)

    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert "not a venue of this build" in result.message
    assert controls.arming[TESTNET].arm_calls == []


def test_a_venue_this_run_does_not_serve_is_refused_not_raised() -> None:
    result = _arm(MemoryControls(TESTNET), "spot_mainnet", "spot_mainnet")

    assert result.refusal is BotRefusal.VENUE_NOT_READY
    assert "does not serve spot_mainnet" in result.message


def test_a_venue_that_already_has_a_strategy_armed_is_refused_and_names_it() -> None:
    controls = MemoryControls(TESTNET)
    controls.arming[TESTNET].armed = ArmedStrategyConfig(
        "rsi_reversion", "ETHUSDT", "1h"
    )

    result = _arm(controls, "spot_testnet")

    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert "already armed" in result.message and "rsi_reversion" in result.message
    assert "`bot disarm-strategy`" in result.message
    assert controls.arming[TESTNET].arm_calls == []


def test_no_saved_arming_is_refused_with_the_way_to_make_one() -> None:
    controls = MemoryControls(TESTNET)
    controls.arming[TESTNET].saved = ArmedStrategyConfig("", "", "")

    result = _arm(controls, "spot_testnet")

    assert result.refusal is BotRefusal.INVALID_DEFINITION
    assert "no saved arming" in result.message and "Arm strategy" in result.message
    assert controls.arming[TESTNET].arm_calls == []


@pytest.mark.parametrize(
    ("reason", "refusal", "words"),
    [
        (
            ArmStrategyBlockReason.SYMBOL_LEASED,
            BotRefusal.SYMBOL_LEASED,
            "managed by another strategy",
        ),
        (
            ArmStrategyBlockReason.SESSION_NOT_READY,
            BotRefusal.VENUE_NOT_READY,
            "could not start",
        ),
        (
            ArmStrategyBlockReason.INVALID_PARAMS,
            BotRefusal.INVALID_DEFINITION,
            "invalid",
        ),
        (
            ArmStrategyBlockReason.POSITION_OPEN,
            BotRefusal.INVALID_TRANSITION,
            "position is open",
        ),
    ],
    ids=["leased", "session", "params", "position"],
)
def test_the_tabs_refusals_reach_the_operator_in_the_tabs_words(
    reason: ArmStrategyBlockReason, refusal: BotRefusal, words: str
) -> None:
    controls = MemoryControls(TESTNET)
    controls.arming[TESTNET].arm_refusal = refused(reason, "fast must be below slow")

    result = _arm(controls, "spot_testnet")

    assert result.refusal is refusal and words in result.message
    assert "fast must be below slow" in result.message
    assert result.message.count("..") == 0 and result.message.endswith(
        "Nothing was armed."
    )
    assert controls.arming[TESTNET].armed is None


def test_a_refusal_with_no_reason_still_says_nothing_was_armed() -> None:
    controls = MemoryControls(TESTNET)
    controls.arming[TESTNET].arm_refusal = ArmStrategyResult(armed=False)

    result = _arm(controls, "spot_testnet")

    assert not result.accepted and "no reason reported" in result.message


def test_disarming_removes_the_strategy_and_says_nothing_was_sold() -> None:
    controls = MemoryControls(TESTNET)
    controls.arming[TESTNET].armed = SAVED

    result = DisarmStrategyForHostCommandHandler(controls).execute(
        DisarmStrategyForHostCommand("spot_testnet")
    )

    assert result.accepted and controls.arming[TESTNET].armed is None
    assert "nothing was sold or cancelled" in result.message


def test_a_disarm_with_a_position_open_is_refused_in_the_tabs_words_and_the_strategy_stays() -> (
    None
):
    controls = MemoryControls(MAINNET)
    controls.arming[MAINNET].armed = SAVED
    controls.arming[MAINNET].position_open = True

    result = DisarmStrategyForHostCommandHandler(controls).execute(
        DisarmStrategyForHostCommand("spot_mainnet")
    )

    assert result.refusal is BotRefusal.INVALID_TRANSITION
    assert "position is open" in result.message and "Emergency stop" in result.message
    assert controls.arming[MAINNET].armed == SAVED


@pytest.mark.parametrize("venue", ["spot_testnet", "nowhere"])
def test_a_disarm_of_nothing_or_of_no_venue_is_refused_and_disarms_nothing(
    venue: str,
) -> None:
    controls = MemoryControls(TESTNET)

    result = DisarmStrategyForHostCommandHandler(controls).execute(
        DisarmStrategyForHostCommand(venue)
    )

    assert not result.accepted
    assert controls.arming[TESTNET].disarm_calls == 0


def test_a_disarm_on_a_venue_this_run_does_not_serve_is_refused_not_raised() -> None:
    result = DisarmStrategyForHostCommandHandler(MemoryControls(TESTNET)).execute(
        DisarmStrategyForHostCommand("spot_mainnet")
    )

    assert result.refusal is BotRefusal.VENUE_NOT_READY
