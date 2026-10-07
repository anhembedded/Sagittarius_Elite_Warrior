"""`EPIC-022B` — handler for `DisarmStrategyCommand`."""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.armed_strategy_changed_event import (
    ArmedStrategyChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)

logger = logging.getLogger("App.CommandHandler")


class DisarmStrategyCommandHandler(
    ICommandHandler[DisarmStrategyCommand, DisarmStrategyResult]
):
    """@brief Clears the armed strategy, unless it holds an open position.

    @details Disarming while the strategy's symbol has a position open is
    refused for the mirror image of `ArmStrategyCommandHandler`'s reason: it
    would leave that position with nothing planning its exit. It was refused
    while trading was enabled (`EPIC-022B`); with no switch (`EPIC-034C`) the
    cause itself refuses, and only while the session is open — a closed one
    knows no positions. `ITradingSession.emergency_stop()` remains the way out:
    it closes the session and the positions, and is not gated on any of this.

    `EPIC-033K` stage 3 — a disarm that took effect publishes
    `ArmedStrategyChangedEvent`, as an arm does.
    """

    def __init__(
        self,
        sessions: VenueStrategySessions,
        trading_ports: IVenueTradingPorts,
        publisher: IEventPublisher,
    ) -> None:
        self._sessions = sessions
        self._trading_ports = trading_ports
        self._publisher = publisher

    def execute(self, command: DisarmStrategyCommand) -> DisarmStrategyResult:
        logger.debug("Handling DisarmStrategyCommand on %s", command.venue.value)
        session = self._sessions.get(command.venue)
        trading_session = self._trading_ports.get(command.venue).trading_session
        armed_symbol = session.config.symbol if session.config else None
        snapshot = trading_session.snapshot()
        if (
            snapshot.enabled
            and armed_symbol is not None
            and armed_symbol in snapshot.known_open_symbols
        ):
            return DisarmStrategyResult(
                disarmed=False,
                block_reason=DisarmStrategyBlockReason.POSITION_OPEN,
            )
        session.disarm()
        if armed_symbol is not None:
            trading_session.release_symbol(armed_symbol, STRATEGY_OWNER)
        self._publisher.publish(ArmedStrategyChangedEvent(False, venue=command.venue))
        return DisarmStrategyResult(disarmed=True)
