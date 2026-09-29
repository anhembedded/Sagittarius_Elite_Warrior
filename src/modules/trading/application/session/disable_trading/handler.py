import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.disable_trading.command import (
    DisableTradingCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)

logger = logging.getLogger("App.CommandHandler")


class DisableTradingCommandHandler(ICommandHandler[DisableTradingCommand, None]):
    """
    @brief Handler for `DisableTradingCommand` — the ordinary, user-facing
    path to `TradingSessionState.disable()` (`EPIC-021I`), symmetric with
    `EnableTradingCommandHandler`. `EmergencyStopCommandHandler` also calls
    `disable()` directly, inline, as its own step 1 — see that handler's
    own docstring for why it does not dispatch this command instead.

    @details Never gated on the venue's order capability or connection
    readiness, unlike enabling — turning trading off must always be
    possible, including as the recovery step after a connection is lost
    mid-session. The one refusal is a venue this process does not serve
    (`VenueNotEnabledError`, `EPIC-028B`): there is no session to turn off. Stops
    `IUserDataStream` (a no-op, per its own contract, if it was never
    started — e.g. disabling right after a refused enable).
    """

    def __init__(self, scopes: VenueTradingScopes) -> None:
        self._scopes = scopes

    def execute(self, command: DisableTradingCommand) -> None:
        logger.debug("Handling DisableTradingCommand on %s", command.venue.value)
        scope = self._scopes.get(command.venue)
        was_enabled = scope.session_state.enabled
        scope.session_state.disable()
        scope.ports.user_data_stream.stop()
        if was_enabled:
            logger.info("Trading disabled on %s for this session.", command.venue.value)
