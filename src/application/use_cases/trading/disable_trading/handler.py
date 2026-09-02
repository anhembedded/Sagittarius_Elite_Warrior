import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.application.services.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.disable_trading.command import (
    DisableTradingCommand,
)

logger = logging.getLogger("App.CommandHandler")


class DisableTradingCommandHandler(ICommandHandler[DisableTradingCommand, None]):
    """
    @brief Handler for `DisableTradingCommand` — the one place
    `TradingSessionState.disable()` is ever called (`EPIC-021I`), symmetric
    with `EnableTradingCommandHandler`.

    @details Never gated on `TradingVenue` or connection readiness, unlike
    enabling — turning trading off must always be possible, including as
    the recovery step after a connection is lost mid-session. Stops
    `IUserDataStream` (a no-op, per its own contract, if it was never
    started — e.g. disabling right after a refused enable).
    """

    def __init__(
        self,
        session_state: TradingSessionState,
        user_data_stream: IUserDataStream,
    ) -> None:
        self._session_state = session_state
        self._user_data_stream = user_data_stream

    def execute(self, command: DisableTradingCommand) -> None:
        logger.debug("Handling DisableTradingCommand")
        was_enabled = self._session_state.enabled
        self._session_state.disable()
        self._user_data_stream.stop()
        if was_enabled:
            logger.info("Trading disabled for this session.")
