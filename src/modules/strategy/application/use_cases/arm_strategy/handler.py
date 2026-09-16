"""`EPIC-022B` — handler for `ArmStrategyCommand`."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.live_strategy_session import (
    LiveStrategySession,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy.command import (
    ArmStrategyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.use_cases.arm_strategy.result import (
    ArmStrategyBlockReason,
    ArmStrategyResult,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.strategy_owner import (
    STRATEGY_OWNER,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_session import (
    ITradingSession,
)

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
        trading_session: ITradingSession,
    ) -> None:
        self._session = session
        self._trading_session = trading_session

    def execute(self, command: ArmStrategyCommand) -> ArmStrategyResult:
        config = command.config
        logger.debug("Handling ArmStrategyCommand for '%s'", config.strategy_key)

        if self._trading_session.snapshot().enabled:
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

        # `EPIC-025` PR 2.1f — claim the symbol BEFORE arming, so a refused
        # claim means nothing was armed. The reverse order would arm a strategy
        # and then discover it may not have the symbol, leaving a live engine
        # to unwind. A claim cannot be refused today (one armed strategy means
        # one owner), which is exactly why the order has to be the one that
        # stays correct when ADR §7 item 15's second strategy arrives.
        if not self._trading_session.claim_symbol(config.symbol, STRATEGY_OWNER):
            logger.info(
                "Refused to arm '%s': %s is managed by another owner.",
                config.strategy_key,
                config.symbol,
            )
            return ArmStrategyResult(
                armed=False, block_reason=ArmStrategyBlockReason.SYMBOL_LEASED
            )

        try:
            self._session.arm(config)
        except ValueError as exc:
            logger.info(
                "Refused to arm '%s': %s", config.strategy_key, exc, exc_info=False
            )
            # The claim was this call's, so this call gives it back. Leaving it
            # held would block the user's own next manual order on a symbol no
            # strategy is running.
            self._trading_session.release_symbol(config.symbol, STRATEGY_OWNER)
            return ArmStrategyResult(
                armed=False,
                block_reason=ArmStrategyBlockReason.INVALID_PARAMS,
                error_message=str(exc),
            )
        return ArmStrategyResult(armed=True)
