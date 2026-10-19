"""`BUG-203` (review of #580) - trading no longer warns about a snapshot divergence, so the bot
that is in no state to confirm one says it.

@details A halt can leave the owner's book installed and the position open on the exchange
(`left_open_words`), and the watch acts only in `PRICE_STALENESS_HALTS`. A divergence that reaches
it, or is still pending when the bot halts, is a WARNING rather than a silent drop, said after the
recheck delay and only if the bot has not ended meanwhile (its own closing fill lags like an opening).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
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


def _halted() -> _Rig:
    rig = _Rig()
    rig.exchange.still_diverged = _divergence()
    rig.world.executor.facts.on_position_divergence(_divergence())
    rig.world.monotonic.advance(5)
    rig.beat()
    assert rig.world.state() is S.HALTED
    return rig


def _says_cannot_confirm(lines: list[str]) -> bool:
    return any(
        "cannot confirm a position divergence" in line
        and "[position-divergence]" in line
        for line in lines
    )


def test_a_divergence_reported_to_a_halted_bot_is_warned_about_once_the_delay_passes() -> (
    None
):
    rig = _halted()
    mismatch = _divergence(PositionDivergenceKind.POSITION_MISMATCH)

    soon = _warned_by(lambda: rig.world.executor.facts.on_position_divergence(mismatch))
    rig.world.monotonic.advance(5)
    later = _warned_by(rig.beat)
    again = _warned_by(rig.beat)

    assert not _says_cannot_confirm(soon), (
        "inside the delay it may be the close's own fill"
    )
    assert _says_cannot_confirm(later)
    assert not _says_cannot_confirm(again), "said once"


def test_a_pending_divergence_dropped_because_the_bot_halted_is_warned_about() -> None:
    rig = _Rig()
    rig.world.executor.facts.on_position_divergence(_divergence())
    rig.world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    rig.world.monotonic.advance(5)

    lines = _warned_by(rig.beat)

    assert _says_cannot_confirm(lines)


def test_a_bot_that_ends_inside_the_delay_says_nothing_about_its_own_closing_fill() -> (
    None
):
    """The close a stop sends lags the account's report as an opening does: a bot that reaches
    STOPPED within the recheck delay (its book cleared) has nothing left to confirm."""
    rig = _Rig()
    rig.world.executor.stop(ExposureHandling.KEEP)
    assert rig.world.state() is S.STOPPED
    rig.world.executor.facts.on_position_divergence(_divergence())
    rig.world.monotonic.advance(5)

    lines = _warned_by(rig.beat)

    assert not _says_cannot_confirm(lines)
