"""`EPIC-022B` — handler for `DisarmStrategyCommand`."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.venue_strategy_sessions import (
    VenueStrategySessions,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.disarm_strategy.command import (
    DisarmStrategyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.disarm_strategy_result import (
    DisarmStrategyBlockReason,
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_owner import (
    STRATEGY_OWNER,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)

logger = logging.getLogger("App.CommandHandler")


class DisarmStrategyCommandHandler(
    ICommandHandler[DisarmStrategyCommand, DisarmStrategyResult]
):
    """@brief Clears the armed strategy, unless trading is on.

    @details Disarming while trading is enabled is refused for the mirror
    image of `ArmStrategyCommandHandler`'s reason: it would produce a
    session that reports "trading is ON" while nothing can ever generate
    a signal, which is precisely the untruthful state this epic exists to
    remove. `ITradingSession.emergency_stop()` remains the way out of a live
    session: it disables trading first, and is not gated on any of this.
    """

    def __init__(
        self, sessions: VenueStrategySessions, trading_ports: IVenueTradingPorts
    ) -> None:
        self._sessions = sessions
        self._trading_ports = trading_ports

    def execute(self, command: DisarmStrategyCommand) -> DisarmStrategyResult:
        logger.debug("Handling DisarmStrategyCommand on %s", command.venue.value)
        session = self._sessions.get(command.venue)
        trading_session = self._trading_ports.get(command.venue).trading_session
        if trading_session.snapshot().enabled:
            return DisarmStrategyResult(
                disarmed=False,
                block_reason=DisarmStrategyBlockReason.TRADING_IS_ENABLED,
            )
        armed_symbol = session.config.symbol if session.config else None
        session.disarm()
        if armed_symbol is not None:
            trading_session.release_symbol(armed_symbol, STRATEGY_OWNER)
        return DisarmStrategyResult(disarmed=True)
