"""`BUG-203` (review of #580) - trading no longer warns about a snapshot divergence, so the bot
that is in no state to confirm one says it.

@details A halt can leave the owner's book installed and the position open on the exchange
(`left_open_words`), and the watch acts only in `PRICE_STALENESS_HALTS`. A divergence that reaches
it, or is still pending when the bot halts, is a WARNING rather than a silent drop.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergenceKind,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.test_grid_risk_watch import (
    _divergence,
    _Rig,
)

S = BotLifecycleState
_LOGGER = "App.Bots.GridExecutor"


class _Warned(logging.Handler):
    """The WARNING-or-worse lines of the bot's logger, which does not propagate to `caplog`."""

    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


def _warned_by(act: object) -> list[str]:
    handler = _Warned()
    logger = logging.getLogger(_LOGGER)
    logger.addHandler(handler)
    try:
        assert callable(act)
        act()
    finally:
        logger.removeHandler(handler)
    return handler.lines


def test_a_divergence_reported_to_a_halted_bot_is_warned_about_not_dropped() -> None:
    rig = _Rig()
    rig.exchange.still_diverged = _divergence()
    rig.world.executor.facts.on_position_divergence(_divergence())
    rig.world.monotonic.advance(5)
    rig.beat()
    assert rig.world.state() is S.HALTED

    lines = _warned_by(
        lambda: rig.world.executor.facts.on_position_divergence(
            _divergence(PositionDivergenceKind.POSITION_MISMATCH)
        )
    )

    assert any(
        "cannot confirm a position divergence" in line
        and "[position-divergence]" in line
        for line in lines
    )


def test_a_pending_divergence_dropped_because_the_bot_halted_is_warned_about() -> None:
    rig = _Rig()
    rig.world.executor.facts.on_position_divergence(_divergence())
    rig.world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)

    lines = _warned_by(rig.beat)

    assert any("cannot confirm a position divergence" in line for line in lines)
