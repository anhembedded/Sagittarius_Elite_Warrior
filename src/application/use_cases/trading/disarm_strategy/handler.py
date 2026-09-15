"""`EPIC-022B` — handler for `DisarmStrategyCommand`."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.disarm_strategy.command import (
    DisarmStrategyCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.disarm_strategy.result import (
    DisarmStrategyBlockReason,
    DisarmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
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
        self,
        session: LiveStrategySession,
        trading_session: ITradingSession,
    ) -> None:
        self._session = session
        self._trading_session = trading_session

    def execute(self, command: DisarmStrategyCommand) -> DisarmStrategyResult:
        logger.debug("Handling DisarmStrategyCommand")
        if self._trading_session.snapshot().enabled:
            return DisarmStrategyResult(
                disarmed=False,
                block_reason=DisarmStrategyBlockReason.TRADING_IS_ENABLED,
            )
        self._session.disarm()
        return DisarmStrategyResult(disarmed=True)
