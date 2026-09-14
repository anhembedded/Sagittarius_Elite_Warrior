"""`EPIC-022B` — handler for `ArmStrategyCommand`."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.arm_strategy.command import (
    ArmStrategyCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.arm_strategy.result import (
    ArmStrategyBlockReason,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler

logger = logging.getLogger("App.CommandHandler")


class ArmStrategyCommandHandler(ICommandHandler[ArmStrategyCommand, ArmStrategyResult]):
    """
    @brief The only place `LiveStrategySession.arm()` is called from the UI
    — where "may this be armed at all" is decided.

    @details Order of checks is deliberate, cheapest and most important
    first:

    1. **Trading is on** → refuse. This is a safety rule, not a
       convenience one (`EPIC-022` §4.1), so it is checked before any
       work that could succeed and make refusing look arbitrary.
    2. **Symbol/interval present** → an incomplete config can never be
       armed; `LiveStrategySession.arm()` would raise, and a raised
       exception is not a UI-branchable answer.
    3. **Strategy key known** → asked of the same `StrategyRegistry` the
       factory will build from, not a second one resolved separately.
    4. **Parameters accepted** → by building it. `BaseStrategy.__init__`
       already raises `ValueError` for an undeclared name and each
       `input_*()` enforces its own `minval`/`maxval`, so re-validating
       here would create a second validator free to disagree with the
       strategy's own. The build that validates is the build that gets
       armed — there is no window where a config passes validation and
       then fails to construct.
    """

    def __init__(
        self,
        session: LiveStrategySession,
        session_state: TradingSessionState,
    ) -> None:
        self._session = session
        self._session_state = session_state

    def execute(self, command: ArmStrategyCommand) -> ArmStrategyResult:
        config = command.config
        logger.debug("Handling ArmStrategyCommand for '%s'", config.strategy_key)

        if self._session_state.enabled:
            return ArmStrategyResult(
                armed=False, block_reason=ArmStrategyBlockReason.TRADING_IS_ENABLED
            )
        if not config.strategy_key:
            return ArmStrategyResult(
                armed=False, block_reason=ArmStrategyBlockReason.STRATEGY_NOT_FOUND
            )
        if not config.symbol or not config.interval:
            return ArmStrategyResult(
                armed=False,
                block_reason=ArmStrategyBlockReason.MISSING_SYMBOL_OR_INTERVAL,
            )
        if config.strategy_key not in self._session.available_strategy_keys:
            return ArmStrategyResult(
                armed=False, block_reason=ArmStrategyBlockReason.STRATEGY_NOT_FOUND
            )

        try:
            self._session.arm(config)
        except ValueError as exc:
            logger.info(
                "Refused to arm '%s': %s", config.strategy_key, exc, exc_info=False
            )
            return ArmStrategyResult(
                armed=False,
                block_reason=ArmStrategyBlockReason.INVALID_PARAMS,
                error_message=str(exc),
            )
        return ArmStrategyResult(armed=True)
