"""What `StrategyArmingCoordinator`'s tests are built from: the form's exact
shape and the coordinator over the strategy module's own fakes."""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.contracts.param_field import ParamGroup
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_arming_coordinator import (
    StrategyArmingCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_arming_control_adapter import (
    StrategyArmingControlAdapter,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.adapters.strategy_catalog_reader_adapter import (
    StrategyCatalogReaderAdapter,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOwnershipTracker,
)

TEST_STRATEGY_KEY = "ema_crossover"


class FakeCardViewModel:
    """The Protocol's exact shape, nothing more — a double built from the
    calls the coordinator makes would pass no matter what it forgot to
    apply (`pitfalls/tests.md` #5), so this implements what
    `StrategyArmingCoordinator`'s `StrategyFormState` declares instead."""

    def __init__(self) -> None:
        self.selected_strategy_key = ""
        self.live_interval = ""
        self.sizing_percent = 0.0
        self.leverage = 0.0
        self.strategy_options: list[tuple[str, str]] = []
        self.interval_options: list[str] = []
        self.bot_params_groups: tuple[ParamGroup, ...] = ()
        self.bot_params_error = ""

    def set_strategy_options(
        self,
        strategy_options: Sequence[tuple[str, str]],
        interval_options: Sequence[str],
    ) -> None:
        self.strategy_options = list(strategy_options)
        self.interval_options = list(interval_options)

    def set_strategy_selection(
        self, strategy_key: str, interval: str, sizing_percent: float, leverage: float
    ) -> None:
        self.selected_strategy_key = strategy_key
        self.live_interval = interval
        self.sizing_percent = sizing_percent
        self.leverage = leverage

    def set_bot_params(self, groups: tuple[ParamGroup, ...]) -> None:
        self.bot_params_groups = groups

    def set_bot_params_error(self, message: str) -> None:
        self.bot_params_error = message


def coordinator_for(view_model, catalog, arming, armed=None, notifier=None):
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
        notifier=notifier or RecordingNotifier(),
        append_log=lambda _line: None,
        on_armed_changed=lambda _config, _busy: None,
    )
