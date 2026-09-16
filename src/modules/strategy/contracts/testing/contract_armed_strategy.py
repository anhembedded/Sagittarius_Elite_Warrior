"""The contract suite for `IArmedStrategy` (HLD §10.3).

The port has one method and the guarantees are about **what one answer means**.

**Disarmed is an answer, not an absence.** `armed()` always returns a snapshot;
a caller must not have to distinguish "nothing armed" from "the port failed".

**The two fields are two facts.** `config` is what the user armed,
`engine_running` is whether an engine was built from it. They agree in every
ordinary state and can disagree between recording a config and finishing the
engine, which is the whole reason the snapshot carries both — see
`ArmedStrategySnapshot`'s docstring for the call site that needs it.

**One answer is one instant.** A caller must be able to compare the two fields
with each other; reading them separately is what the real session used to force,
and this suite is what stops an implementation going back to it.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_armed_strategy import (
    IArmedStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.live_strategy_config import (
    LiveStrategyConfig,
)

#: How a subclass arms its implementation — the fake seeds, the real session is
#: armed through its own `arm()`.
type Arm = Callable[[LiveStrategyConfig], None]


class ArmedStrategyContract:
    """Inherit this, provide `impl`, `arm` and `a_config`."""

    @pytest.fixture
    def impl(self) -> IArmedStrategy:
        raise NotImplementedError(
            "an ArmedStrategyContract subclass must provide an `impl` fixture"
        )

    @pytest.fixture
    def arm(self) -> Arm:
        raise NotImplementedError(
            "an ArmedStrategyContract subclass must provide an `arm` fixture"
        )

    @pytest.fixture
    def a_config(self) -> LiveStrategyConfig:
        """Concrete, unlike `impl` and `arm`: what a valid armed config *is*
        belongs to the contract, not to whoever implements it, and a fixture a
        subclass must remember to provide is a fixture a subclass can forget.
        A class-level fixture also wins over a module-level one, so a subclass
        defining this at module scope would silently not override it — which is
        how this suite first failed."""
        return LiveStrategyConfig(
            strategy_key="ema_crossover",
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_MINUTE.value,
        )

    def test_disarmed_is_a_snapshot_not_a_none(self, impl: IArmedStrategy) -> None:
        snapshot = impl.armed()

        assert snapshot.config is None
        assert snapshot.engine_running is False

    def test_arming_shows_in_both_fields(
        self, impl: IArmedStrategy, arm: Arm, a_config: LiveStrategyConfig
    ) -> None:
        arm(a_config)
        snapshot = impl.armed()

        assert snapshot.config == a_config
        assert snapshot.engine_running is True

    def test_the_snapshot_is_frozen(
        self, impl: IArmedStrategy, arm: Arm, a_config: LiveStrategyConfig
    ) -> None:
        """It crosses to two screens; one must not be able to edit what the
        other sees."""
        arm(a_config)
        snapshot = impl.armed()

        with pytest.raises((AttributeError, TypeError)):
            snapshot.engine_running = False  # type: ignore[misc]

    def test_a_later_arming_does_not_change_a_snapshot_already_given(
        self, impl: IArmedStrategy, arm: Arm, a_config: LiveStrategyConfig
    ) -> None:
        """A snapshot is an instant. An implementation answering with a live
        view of its own state would make "what was armed when I checked"
        unanswerable — which is what the caller in `dashboard_presenter` is
        deciding a manual order against."""
        held = impl.armed()

        arm(a_config)

        assert held.config is None
        assert held.engine_running is False
