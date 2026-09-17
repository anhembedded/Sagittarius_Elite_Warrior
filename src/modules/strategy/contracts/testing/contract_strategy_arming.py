"""The contract suite for `IStrategyArming` (HLD §10.3).

**`saved_selection()` never returns `None`.** An empty, incomplete
`LiveStrategyConfig` (`is_complete` is `False`) is "nothing saved yet",
matching `IArmedStrategy.armed()`'s own "disarmed is a snapshot, not an
absence" guarantee.

**A successful arm is the one thing that changes what `saved_selection()`
answers.** This is the behaviour `LiveStrategyConfigStore.save()` used to
provide from the caller's side (`ArmStrategyCommandHandler`'s own docstring
before PR 4.3m); moving it inside `arm()` must not lose it.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_arming import (
    IStrategyArming,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)


class StrategyArmingContract:
    """Inherit this, provide `impl`."""

    @pytest.fixture
    def impl(self) -> IStrategyArming:
        raise NotImplementedError(
            "a StrategyArmingContract subclass must provide an `impl` fixture"
        )

    @pytest.fixture
    def a_config(self) -> LiveStrategyConfig:
        return LiveStrategyConfig(
            strategy_key="ema_crossover", symbol="BTCUSDT", interval="1m"
        )

    def test_saved_selection_starts_as_nothing_saved_not_none(
        self, impl: IStrategyArming
    ) -> None:
        saved = impl.saved_selection()

        assert saved is not None
        assert saved.is_complete is False

    def test_a_successful_arm_becomes_the_saved_selection(
        self, impl: IStrategyArming, a_config: LiveStrategyConfig
    ) -> None:
        result = impl.arm(a_config)

        if result.armed:
            assert impl.saved_selection() == a_config
