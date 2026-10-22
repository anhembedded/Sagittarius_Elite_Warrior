"""`EPIC-045G` - the host's "remove this venue's armed strategy", answered by the screen's own Disarm strategy.

It asks the very `IStrategyArmingControl.disarm` the tab asks, so the position check is the tab's: a position
open on the strategy's symbol refuses it, in the tab's words. Disarming sells and cancels nothing, so it asks
no venue confirmation, on a mainnet venue too (the tab asks none). A venue this run does not serve and a venue
with nothing armed are refused in words, so an operator who typed it twice learns that nothing changed.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import STRATEGY_SUBJECT
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_identity import (
    venue_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.strategy.strategy_arm_words import (
    DISARM_BLOCKED_WORDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    DisarmStrategyForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class DisarmStrategyForHostCommandHandler(
    ICommandHandler[DisarmStrategyForHostCommand, BotCommandResult]
):
    def __init__(self, controls: IVenueStrategyControls) -> None:
        self._controls = controls

    def execute(self, command: DisarmStrategyForHostCommand) -> BotCommandResult:
        venue = venue_of(command.venue)
        if not isinstance(venue, TradingVenue):
            return _refused(BotRefusal.INVALID_DEFINITION, venue)
        try:
            ports = self._controls.get(venue)
        except VenueNotEnabledError as not_served:
            return _refused(
                BotRefusal.VENUE_NOT_READY,
                f"this run does not serve {venue.value}, so no strategy is armed on it "
                f"({not_served})",
            )
        armed = ports.armed.armed().config
        if armed is None:
            return _refused(
                BotRefusal.INVALID_TRANSITION,
                f"no strategy is armed on {venue.value}",
            )
        if not ports.arming.disarm().disarmed:
            return _refused(
                BotRefusal.INVALID_TRANSITION, DISARM_BLOCKED_WORDS.rstrip(".")
            )
        return BotCommandResult(
            accepted=True,
            bot_id=STRATEGY_SUBJECT,
            message=(
                f"the {armed.strategy_key} strategy on {armed.symbol} was removed from "
                f"{venue.value}; nothing was sold or cancelled"
            ),
        )


def _refused(refusal: BotRefusal, words: str) -> BotCommandResult:
    return BotCommandResult.refused(
        refusal, f"{words}. Nothing was changed.", STRATEGY_SUBJECT
    )
