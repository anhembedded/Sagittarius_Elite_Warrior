"""`EPIC-022D`/`EPIC-022F` — the Trading screen's strategy card.

The assertions here are mostly about what must NOT happen: picking a
strategy must not arm it, restoring config must not run anything, and a
refusal must reach the user as words rather than as a button that appears
to do nothing. Those are the failure modes this epic was opened to fix.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.arm_strategy import (
    ArmStrategyBlockReason,
    ArmStrategyCommand,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.disarm_strategy import (
    DisarmStrategyBlockReason,
    DisarmStrategyCommand,
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.strategy_arming_coordinator import (
    StrategyArmingCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.strategy_display import (
    humanize_strategy_key,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.trading.trading_view_model import (
    TradingViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)

#: Mirrors `screens/trading/conftest.py`'s own `TEST_STRATEGY_KEY`. Restated
#: rather than imported: this file moved to `common/` with the coordinator
#: itself (`EPIC-023C`), out of reach of that screen-scoped conftest — same
#: "restate, don't cross-import a test fixture" reasoning this file already
#: applied to the constant below before the move.
TEST_STRATEGY_KEY = "ema_crossover"

_INTERVALS = ["1m", "5m", "1h"]


@pytest.fixture
def strategy_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(TEST_STRATEGY_KEY, EmaCrossoverStrategy)
    return registry


class _FakeConfig:
    """A config that really stores what it is given, so a persistence test
    can assert on the values rather than on `set` having been called."""

    def __init__(self, initial: dict | None = None) -> None:
        self.values = dict(initial or {})
        self.save_count = 0

    def get(self, key, default=None, cast=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        self.save_count += 1


@pytest.fixture
def view_model(qapp) -> TradingViewModel:
    return TradingViewModel()


@pytest.fixture
def dispatcher() -> MagicMock:
    dispatcher = MagicMock()
    dispatcher.dispatch.return_value = ArmStrategyResult(armed=True)
    return dispatcher


def _coordinator(view_model, dispatcher, strategy_registry, config=None, armed=None):
    """@param armed What the session reports as armed, for the tests that
    exercise the summary/status path. Everything the Presenter used to do
    inline is now handed in, so these tests drive the same code the real
    button does rather than a coordinator missing half its collaborators.
    """
    return StrategyArmingCoordinator(
        view_model=view_model,
        config=config or _FakeConfig(),
        dispatcher=dispatcher,
        available_strategies=strategy_registry.available,
        get_active_symbol=lambda: "BTCUSDT",
        get_armed_config=lambda: armed,
        tracker=ActionOwnershipTracker(),
        arm_action_kind="arm_strategy",
        set_status=lambda _message, _is_error: None,
        append_log=lambda _line: None,
        on_armed_changed=lambda _config, _busy: None,
    )


def test_restore_fills_the_card_without_dispatching_anything(
    view_model, dispatcher, strategy_registry
):
    """`BUG-101`/`BUG-104` were both "restoring config quietly ran real
    work". This is the assertion that stops the third occurrence."""
    config = _FakeConfig(
        {
            ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value: TEST_STRATEGY_KEY,
            ConfigKeys.TRADING_LIVE_INTERVAL.value: "5m",
            ConfigKeys.TRADING_LIVE_SIZING_PERCENT.value: 7.5,
            ConfigKeys.TRADING_LIVE_LEVERAGE.value: 3.0,
            ConfigKeys.TRADING_LIVE_STRATEGY_PARAMS.value: '{"fast_period": 8}',
        }
    )
    coordinator = _coordinator(view_model, dispatcher, strategy_registry, config)

    coordinator.restore_into_view_model(_INTERVALS)

    assert view_model.selectedStrategyKey == TEST_STRATEGY_KEY
    assert view_model.liveInterval == "5m"
    assert view_model.sizingPercent == 7.5
    assert view_model.leverage == 3.0
    dispatcher.dispatch.assert_not_called()


def test_restore_leaves_nothing_armed(view_model, dispatcher, strategy_registry):
    """The card shows the saved choice; the engine stays empty until the
    user presses "Nạp chiến lược" themselves."""
    coordinator = _coordinator(view_model, dispatcher, strategy_registry)

    coordinator.restore_into_view_model(_INTERVALS)

    assert view_model.armedSummary == ""


def test_a_saved_key_that_no_longer_exists_falls_back_without_arming(
    view_model, dispatcher, strategy_registry
):
    config = _FakeConfig(
        {ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value: "strategy_deleted_last_year"}
    )
    coordinator = _coordinator(view_model, dispatcher, strategy_registry, config)

    coordinator.restore_into_view_model(_INTERVALS)

    assert view_model.selectedStrategyKey == TEST_STRATEGY_KEY
    dispatcher.dispatch.assert_not_called()


def test_picking_a_strategy_rebuilds_the_form_but_does_not_arm(
    view_model, dispatcher, strategy_registry
):
    coordinator = _coordinator(view_model, dispatcher, strategy_registry)
    coordinator.restore_into_view_model(_INTERVALS)
    dispatcher.dispatch.reset_mock()

    view_model.requestStrategySelection(TEST_STRATEGY_KEY)
    coordinator.refresh_params_rows()

    assert view_model.botParamsRows != []
    dispatcher.dispatch.assert_not_called()


def test_arming_dispatches_the_command_with_what_the_card_shows(
    view_model, dispatcher, strategy_registry
):
    coordinator = _coordinator(view_model, dispatcher, strategy_registry)
    coordinator.restore_into_view_model(_INTERVALS)
    view_model.requestIntervalSelection("1h")
    view_model.requestSizingPercent(12.5)
    view_model.requestLeverage(4.0)

    coordinator.arm()

    command = dispatcher.dispatch.call_args.args[1]
    assert isinstance(command, ArmStrategyCommand)
    assert command.config == LiveStrategyConfig(
        strategy_key=TEST_STRATEGY_KEY,
        symbol="BTCUSDT",
        interval="1h",
        sizing_percent=12.5,
        leverage=4.0,
    )


def test_a_successful_arm_persists_every_field_and_saves_once(
    view_model, dispatcher, strategy_registry
):
    config = _FakeConfig()
    coordinator = _coordinator(view_model, dispatcher, strategy_registry, config)
    coordinator.restore_into_view_model(_INTERVALS)
    view_model.requestIntervalSelection("1m")
    coordinator.apply_params({"fast_period": "9", "slow_period": "21"})

    coordinator.arm()

    assert (
        config.values[ConfigKeys.TRADING_LIVE_STRATEGY_KEY.value] == TEST_STRATEGY_KEY
    )
    assert config.values[ConfigKeys.TRADING_LIVE_INTERVAL.value] == "1m"
    assert config.values[ConfigKeys.TRADING_LIVE_SYMBOL.value] == "BTCUSDT"
    assert json.loads(config.values[ConfigKeys.TRADING_LIVE_STRATEGY_PARAMS.value]) == {
        "fast_period": 9,
        "slow_period": 21,
    }
    assert config.save_count == 1


def test_a_refused_arm_persists_nothing(view_model, dispatcher, strategy_registry):
    """A configuration the strategy rejected is not one to reload next
    session — `_arm_from_config` would fail the same way at boot, with
    nobody around to read the message."""
    config = _FakeConfig()
    dispatcher.dispatch.return_value = ArmStrategyResult(
        armed=False, block_reason=ArmStrategyBlockReason.TRADING_IS_ENABLED
    )
    coordinator = _coordinator(view_model, dispatcher, strategy_registry, config)
    coordinator.restore_into_view_model(_INTERVALS)

    coordinator.arm()

    assert config.values == {}
    assert config.save_count == 0


def test_invalid_parameters_are_reported_and_not_kept(
    view_model, dispatcher, strategy_registry
):
    coordinator = _coordinator(view_model, dispatcher, strategy_registry)
    coordinator.restore_into_view_model(_INTERVALS)

    accepted = coordinator.apply_params({"fast_period": "not a number"})

    assert accepted is False
    assert view_model.botParamsError != ""
    assert coordinator.build_config().strategy_params == {}


def test_disarm_dispatches_the_disarm_command(
    view_model, dispatcher, strategy_registry
):
    dispatcher.dispatch.return_value = DisarmStrategyResult(disarmed=True)
    coordinator = _coordinator(view_model, dispatcher, strategy_registry)
    coordinator.restore_into_view_model(_INTERVALS)

    result = coordinator.disarm()

    assert isinstance(dispatcher.dispatch.call_args.args[1], DisarmStrategyCommand)
    assert result.disarmed is True


def test_a_blocked_disarm_is_reported_not_swallowed(
    view_model, dispatcher, strategy_registry
):
    dispatcher.dispatch.return_value = DisarmStrategyResult(
        disarmed=False, block_reason=DisarmStrategyBlockReason.TRADING_IS_ENABLED
    )
    coordinator = _coordinator(view_model, dispatcher, strategy_registry)

    result = coordinator.disarm()

    assert result.disarmed is False
    assert result.block_reason is DisarmStrategyBlockReason.TRADING_IS_ENABLED


def test_the_armed_summary_distinguishes_two_armings_of_one_strategy(
    view_model, dispatcher, strategy_registry
):
    """Two runs of the same strategy with different periods are different
    bots; a summary that could not tell them apart would be the same kind
    of half-truth this epic removed from the toggle."""
    coordinator = _coordinator(view_model, dispatcher, strategy_registry)
    fast = LiveStrategyConfig(
        strategy_key=TEST_STRATEGY_KEY,
        symbol="BTCUSDT",
        interval="1m",
        strategy_params={"fast_period": 5},
    )
    slow = LiveStrategyConfig(
        strategy_key=TEST_STRATEGY_KEY,
        symbol="BTCUSDT",
        interval="1m",
        strategy_params={"fast_period": 50},
    )

    assert coordinator.armed_summary(fast) != coordinator.armed_summary(slow)
    assert coordinator.armed_summary(None) == ""


def test_humanized_labels_never_replace_the_registry_key(
    view_model, dispatcher, strategy_registry
):
    """The combo shows a label but must arm by key — deriving one from the
    other by string surgery is how a renamed strategy stops being
    armable."""
    coordinator = _coordinator(view_model, dispatcher, strategy_registry)
    coordinator.restore_into_view_model(_INTERVALS)

    options = view_model.strategyOptions

    assert options[0]["key"] == TEST_STRATEGY_KEY
    assert options[0]["label"] == humanize_strategy_key(TEST_STRATEGY_KEY)
    assert options[0]["label"] != options[0]["key"]
