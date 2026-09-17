"""`EPIC-022B` — handler for `DisarmStrategyCommand`."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
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
        # `EPIC-025` PR 2.1f — read the symbol before disarming clears it, and
        # release after, so the lease is given back exactly when the engine
        # that justified it stops existing. `release_symbol` is a no-op when
        # this owner does not hold that symbol, so a disarm with nothing armed
        # needs no special case.
        armed_symbol = self._session.config.symbol if self._session.config else None
        self._session.disarm()
        if armed_symbol is not None:
            self._trading_session.release_symbol(armed_symbol, STRATEGY_OWNER)
        return DisarmStrategyResult(disarmed=True)
