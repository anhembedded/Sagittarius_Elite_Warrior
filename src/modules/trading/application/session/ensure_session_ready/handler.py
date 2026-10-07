from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.ensure_session_ready.command import (
    EnsureSessionReadyCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.session_readiness import (
    SessionReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.session_ready_result import (
    SessionReadyResult,
)

logger = logging.getLogger("App.CommandHandler")


class EnsureSessionReadyCommandHandler(
    ICommandHandler[EnsureSessionReadyCommand, SessionReadyResult]
):
    """@brief Handler for `EnsureSessionReadyCommand` — what Start bot and Arm
    strategy reach through `ITradingSession.ensure_ready()`.

    @details The reconciliation itself is `SessionReadiness`'s, which
    `ExecuteOrderCommandHandler` also calls directly for a manual order
    (`EPIC-034C`): a handler does not dispatch another handler's command.
    """

    def __init__(self, readiness: SessionReadiness) -> None:
        self._readiness = readiness

    def execute(self, command: EnsureSessionReadyCommand) -> SessionReadyResult:
        logger.debug("Handling EnsureSessionReadyCommand on %s", command.venue.value)
        return self._readiness.ensure_ready(command.venue)
