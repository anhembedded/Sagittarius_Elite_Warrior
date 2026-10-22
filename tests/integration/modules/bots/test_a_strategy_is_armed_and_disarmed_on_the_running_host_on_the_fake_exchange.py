"""`EPIC-045G` - `bot arm-strategy` and `bot disarm-strategy` on the composed app over the fake exchange.

@details The owner's rule: what the Bots tab does at runtime the host does too. The tab's Arm strategy arms
the form's values, which it fills from the venue's saved arming; the host arms that saved arming, through the
very `IStrategyArmingControl` the tab asks, so the strategy module's own checks run. The operator's command
files go through the host's own poller. The mainnet confirmation is judged by the unit tests: the fake exchange holds no mainnet key, so a mainnet venue cannot be armed here.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    STRATEGY_SUBJECT,
    HostControlAction,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)

from .grid_fake_exchange import SPOT, FakeExchange, booted, resting
from .host_control_world import operator_of

_LONG_ONLY = ArmedStrategyConfig("ema_crossover", "BTCUSDT", "5m", {}, 10.0, 1.0)


def _arm(venue: str, typed: str | None = None) -> HostControlRequest:
    return HostControlRequest(
        HostControlAction.ARM_STRATEGY,
        STRATEGY_SUBJECT,
        typed,
        strategy_venue=venue,
    )


def _disarm(venue: str) -> HostControlRequest:
    return HostControlRequest(
        HostControlAction.DISARM_STRATEGY, STRATEGY_SUBJECT, strategy_venue=venue
    )


def test_the_host_arms_the_saved_arming_refuses_a_second_and_disarms(
    exchange: FakeExchange, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(exchange.tmp_path))
    with booted(exchange) as app:
        app.stream.start = lambda: None  # type: ignore[method-assign]
        controls = app.engine.context.container.resolve(IVenueStrategyControls).get(
            SPOT
        )
        operator = operator_of(app.engine, exchange.tmp_path, app.deliver)

        no_saved = operator.ask(_arm(SPOT.value))
        saved_once = controls.arming.arm(_LONG_ONLY)
        controls.arming.disarm()
        assert saved_once.armed, "the desktop's arm saves the arming the host then arms"
        assert controls.armed.armed().config is None

        armed = operator.ask(_arm(SPOT.value))
        again = operator.ask(_arm(SPOT.value))
        gone = operator.ask(_disarm(SPOT.value))
        gone_again = operator.ask(_disarm(SPOT.value))

        assert no_saved.status is HostControlStatus.REFUSED
        assert "no saved arming" in no_saved.message
        assert armed.status is HostControlStatus.DONE, armed.message
        assert "ema_crossover" in armed.message and "BTCUSDT" in armed.message
        assert again.status is HostControlStatus.REFUSED
        assert "already armed" in again.message
        assert gone.status is HostControlStatus.DONE, gone.message
        assert controls.armed.armed().config is None
        assert gone_again.status is HostControlStatus.REFUSED
        assert resting(app.urls) == {}, "arming a strategy places no order by itself"
