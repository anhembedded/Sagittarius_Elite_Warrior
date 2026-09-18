"""`EPIC-022D`/`EPIC-022F`/`EPIC-025` PR 4.3m — the shared
`StrategyArmingCoordinator` both Trading and Dev Board construct.

The assertions here are mostly about what must NOT happen: picking a
strategy must not arm it, restoring config must not run anything, and a
refusal must reach the user as words rather than as a button that appears
to do nothing. Those are the failure modes `EPIC-022` was opened to fix.

`PR 4.3m` moved this Coordinator's collaborators onto the two published
ports (`IStrategyCatalog`, `IStrategyArming`); this file replaces
`tests/unit/modules/strategy/ui/test_strategy_arming_coordinator.py`
(deleted with the Coordinator it tested, when that Coordinator still lived
inside `modules/strategy/ui/`) with the same guarantees driven through
the new ports instead of a dispatcher and a hand-rolled config double —
persistence on a successful arm is now `IStrategyArming`'s own concern, so
there is nothing left here to assert about `IConfig`. One test file
suffices because one Coordinator class serves both screens — see the
production file's own docstring for why an earlier draft's two per-screen
copies were wrong.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_arming_control_adapter import (
    StrategyArmingControlAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_catalog_reader_adapter import (
    StrategyCatalogReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_catalog_service import (
    StrategyCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.arm_strategy_result import (
    ArmStrategyBlockReason,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.disarm_strategy_result import (
    DisarmStrategyBlockReason,
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.testing import (
    FakeStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyBlockReason as TradingArmStrategyBlockReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_disarm_result import (
    DisarmStrategyBlockReason as TradingDisarmStrategyBlockReason,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.strategy_arming_coordinator import (
    StrategyArmingCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)

TEST_STRATEGY_KEY = "ema_crossover"
_INTERVALS = ["1m", "5m", "1h"]


class _FakeCardViewModel:
    """The Protocol's exact shape, nothing more — a double built from the
    calls the coordinator makes would pass no matter what it forgot to
    apply (`pitfalls/tests.md` #5), so this implements what
    `StrategyArmingCoordinator.StrategyCardViewModel` declares instead."""

    def __init__(self) -> None:
        self.selectedStrategyKey = ""
        self.liveInterval = ""
        self.sizingPercent = 0.0
        self.leverage = 0.0
        self.strategy_options: list[dict] = []
        self.interval_options: list[str] = []
        self.bot_params_groups: tuple[ParamGroup, ...] = ()
        self.bot_params_error = ""
        self.last_signal_text = ""

    def set_strategy_options(
        self, strategy_options: list[dict], interval_options: list[str]
    ) -> None:
        self.strategy_options = strategy_options
        self.interval_options = interval_options

    def set_strategy_selection(
        self, strategy_key: str, interval: str, sizing_percent: float, leverage: float
    ) -> None:
        self.selectedStrategyKey = strategy_key
        self.liveInterval = interval
        self.sizingPercent = sizing_percent
        self.leverage = leverage

    def set_bot_params(self, groups: tuple[ParamGroup, ...]) -> None:
        self.bot_params_groups = groups

    def set_bot_params_error(self, message: str) -> None:
        self.bot_params_error = message

    def set_last_signal_text(self, text: str) -> None:
        self.last_signal_text = text


@pytest.fixture
def strategy_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(TEST_STRATEGY_KEY, EmaCrossoverStrategy)
    return registry


@pytest.fixture
def catalog(strategy_registry: StrategyRegistry) -> StrategyCatalogService:
    """The real, cheap service over an in-memory registry, not a `Mock`:
    `testing-rule.md` §2 prefers the real thing when it costs nothing."""
    return StrategyCatalogService(strategy_registry)


@pytest.fixture
def arming() -> FakeStrategyArming:
    return FakeStrategyArming()


@pytest.fixture
def view_model() -> _FakeCardViewModel:
    return _FakeCardViewModel()


def _coordinator(view_model, catalog, arming, armed=None):
    """Wraps the raw strategy-owned `catalog`/`arming` fakes with the same
    adapters `StrategyModule.register()` binds in production
    (`EPIC-025` PR 4.4c §8) — the coordinator now talks to trading's own
    `IStrategyCatalogReader`/`IStrategyArmingControl`, never the
    strategy-owned ports directly. Tests still script and introspect the
    RAW fake (`arming.armed_with`, `arming.script_arm()`, …), on the other
    side of that same adapter."""
    return StrategyArmingCoordinator(
        view_model=view_model,
        catalog=StrategyCatalogReaderAdapter(catalog),
        arming=StrategyArmingControlAdapter(arming),
        get_active_symbol=lambda: "BTCUSDT",
        get_armed_config=lambda: armed,
        tracker=ActionOwnershipTracker(),
        arm_action_kind="arm_strategy",
        set_status=lambda _message, _is_error: None,
        append_log=lambda _line: None,
        on_armed_changed=lambda _config, _busy: None,
    )


def _seed_saved_selection(
    arming: FakeStrategyArming, config: LiveStrategyConfig
) -> None:
    """`FakeStrategyArming` only offers `arm()` to set what `saved_selection()`
    later returns, and `arm()` also records `armed_with` — a seed for
    "what a previous session left saved" is not "what this test's own
    action armed", so this bypasses `arm()` and writes the fake's
    in-memory state directly, the same as any other hand-built double."""
    arming._saved = config


def test_restore_fills_the_card_without_arming(view_model, catalog, arming):
    """`BUG-101`/`BUG-104` were both "restoring config quietly ran real
    work". This is the assertion that stops the third occurrence."""
    _seed_saved_selection(
        arming,
        LiveStrategyConfig(
            strategy_key=TEST_STRATEGY_KEY,
            symbol="BTCUSDT",
            interval="5m",
            sizing_percent=7.5,
            leverage=3.0,
            strategy_params={"fast_period": 8},
        ),
    )
    coordinator = _coordinator(view_model, catalog, arming)

    coordinator.restore_into_view_model(_INTERVALS)

    assert view_model.selectedStrategyKey == TEST_STRATEGY_KEY
    assert view_model.liveInterval == "5m"
    assert view_model.sizingPercent == 7.5
    assert view_model.leverage == 3.0
    assert arming.armed_with is None


def test_restore_leaves_nothing_armed(view_model, catalog, arming):
    """The card shows the saved choice; the engine stays empty until the
    user presses "Nạp chiến lược" themselves."""
    coordinator = _coordinator(view_model, catalog, arming)

    coordinator.restore_into_view_model(_INTERVALS)

    assert coordinator.armed_summary(None) == ""


def test_a_saved_key_that_no_longer_exists_falls_back_without_arming(
    view_model, catalog, arming
):
    _seed_saved_selection(
        arming,
        LiveStrategyConfig(
            strategy_key="strategy_deleted_last_year", symbol="", interval="1m"
        ),
    )
    coordinator = _coordinator(view_model, catalog, arming)

    coordinator.restore_into_view_model(_INTERVALS)

    assert view_model.selectedStrategyKey == TEST_STRATEGY_KEY
    assert arming.armed_with is None


def test_picking_a_strategy_rebuilds_the_form_but_does_not_arm(
    view_model, catalog, arming
):
    coordinator = _coordinator(view_model, catalog, arming)
    coordinator.restore_into_view_model(_INTERVALS)

    coordinator.on_strategy_selection_changed()

    assert view_model.bot_params_groups != ()
    assert arming.armed_with is None


def test_arming_calls_the_port_with_what_the_card_shows(view_model, catalog, arming):
    coordinator = _coordinator(view_model, catalog, arming)
    coordinator.restore_into_view_model(_INTERVALS)
    view_model.liveInterval = "1h"
    view_model.sizingPercent = 12.5
    view_model.leverage = 4.0

    coordinator.arm()

    assert arming.armed_with == LiveStrategyConfig(
        strategy_key=TEST_STRATEGY_KEY,
        symbol="BTCUSDT",
        interval="1h",
        strategy_params={},
        sizing_percent=12.5,
        leverage=4.0,
    )


def test_invalid_parameters_are_reported_and_not_kept(view_model, catalog, arming):
    coordinator = _coordinator(view_model, catalog, arming)
    coordinator.restore_into_view_model(_INTERVALS)

    accepted = coordinator.apply_params({"fast_period": "not a number"})

    assert accepted is False
    assert view_model.bot_params_error != ""
    assert coordinator.build_config().strategy_params == {}


def test_valid_parameters_are_kept_and_carried_into_the_armed_config(
    view_model, catalog, arming
):
    coordinator = _coordinator(view_model, catalog, arming)
    coordinator.restore_into_view_model(_INTERVALS)

    accepted = coordinator.apply_params({"fast_period": "9", "slow_period": "21"})

    assert accepted is True
    assert coordinator.build_config().strategy_params == {
        "fast_period": 9,
        "slow_period": 21,
    }


def test_a_refused_arm_is_reported_by_the_ports_own_result(view_model, catalog, arming):
    arming.script_arm(
        ArmStrategyResult(
            armed=False, block_reason=ArmStrategyBlockReason.TRADING_IS_ENABLED
        )
    )
    coordinator = _coordinator(view_model, catalog, arming)
    coordinator.restore_into_view_model(_INTERVALS)

    result = coordinator.arm()

    assert result.armed is False
    assert result.block_reason is TradingArmStrategyBlockReason.TRADING_IS_ENABLED


def test_disarm_calls_the_port(view_model, catalog, arming):
    arming.script_disarm(DisarmStrategyResult(disarmed=True))
    coordinator = _coordinator(view_model, catalog, arming)
    coordinator.restore_into_view_model(_INTERVALS)

    result = coordinator.disarm()

    assert arming.disarm_calls == 1
    assert result.disarmed is True


def test_a_blocked_disarm_is_reported_not_swallowed(view_model, catalog, arming):
    arming.script_disarm(
        DisarmStrategyResult(
            disarmed=False, block_reason=DisarmStrategyBlockReason.TRADING_IS_ENABLED
        )
    )
    coordinator = _coordinator(view_model, catalog, arming)

    result = coordinator.disarm()

    assert result.disarmed is False
    assert result.block_reason is TradingDisarmStrategyBlockReason.TRADING_IS_ENABLED


def test_the_armed_summary_distinguishes_two_armings_of_one_strategy(
    view_model, catalog, arming
):
    """Two runs of the same strategy with different periods are different
    bots; a summary that could not tell them apart would be the same kind
    of half-truth this epic removed from the toggle."""
    coordinator = _coordinator(view_model, catalog, arming)
    fast = ArmedStrategyConfig(
        strategy_key=TEST_STRATEGY_KEY,
        symbol="BTCUSDT",
        interval="1m",
        strategy_params={"fast_period": 5},
    )
    slow = ArmedStrategyConfig(
        strategy_key=TEST_STRATEGY_KEY,
        symbol="BTCUSDT",
        interval="1m",
        strategy_params={"fast_period": 50},
    )

    assert coordinator.armed_summary(fast) != coordinator.armed_summary(slow)
    assert coordinator.armed_summary(None) == ""


def test_humanized_labels_never_replace_the_catalog_key(view_model, catalog, arming):
    """The combo shows a label but must arm by key — deriving one from the
    other by string surgery is how a renamed strategy stops being
    armable."""
    coordinator = _coordinator(view_model, catalog, arming)
    coordinator.restore_into_view_model(_INTERVALS)

    options = view_model.strategy_options

    assert options[0]["key"] == TEST_STRATEGY_KEY
    assert options[0]["label"] != options[0]["key"]
    assert coordinator.armed_summary(
        ArmedStrategyConfig(
            strategy_key=TEST_STRATEGY_KEY, symbol="BTCUSDT", interval="1m"
        )
    ).startswith(options[0]["label"])


def _signal_event(symbol: str):
    from datetime import UTC, datetime

    from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal import Signal
    from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
        SignalAction,
    )
    from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.signal_generated_event import (
        SignalGeneratedEvent,
    )

    signal = Signal(
        symbol=symbol,
        action=SignalAction.BUY,
        reason="RSI Oversold",
        price=64000.0,
        time=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
    )
    return SignalGeneratedEvent(signal=signal)


def test_on_signal_generated_updates_the_card_for_the_armed_symbol(
    view_model, catalog, arming
):
    """`SignalFeed.signalGenerated` connects straight to this method now
    (`EPIC-025` PR 4.3m) — no per-screen `_on_signal_generated` wrapper
    left to duplicate."""
    armed = ArmedStrategyConfig(
        strategy_key=TEST_STRATEGY_KEY, symbol="BTCUSDT", interval="1m"
    )
    coordinator = _coordinator(view_model, catalog, arming, armed=armed)

    coordinator.on_signal_generated(_signal_event("BTCUSDT"))

    assert "BUY" in view_model.last_signal_text
    assert "RSI Oversold" in view_model.last_signal_text


def test_on_signal_generated_for_a_different_symbol_is_ignored(
    view_model, catalog, arming
):
    """A backtest run's own `StrategyEngine` publishes on the same bus —
    this is the filter that keeps its output off a live card."""
    armed = ArmedStrategyConfig(
        strategy_key=TEST_STRATEGY_KEY, symbol="BTCUSDT", interval="1m"
    )
    coordinator = _coordinator(view_model, catalog, arming, armed=armed)

    coordinator.on_signal_generated(_signal_event("ETHUSDT"))

    assert view_model.last_signal_text == ""


def test_on_signal_generated_with_nothing_armed_is_ignored(view_model, catalog, arming):
    coordinator = _coordinator(view_model, catalog, arming, armed=None)

    coordinator.on_signal_generated(_signal_event("BTCUSDT"))

    assert view_model.last_signal_text == ""
