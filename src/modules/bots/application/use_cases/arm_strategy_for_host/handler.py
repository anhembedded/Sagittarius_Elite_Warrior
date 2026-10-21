"""`EPIC-045G` - the host's "arm this venue's strategy", answered by the screen's own Arm strategy.

The Bots tab's Arm strategy fills a form from the venue's saved arming and arms what the form holds
through `IStrategyArmingControl.arm`. The host has no form, so the owner's decision (O2, 2026-10-21) is
that it arms **the saved arming**: the strategy, symbol, interval, sizing, leverage and parameters the last
successful arm saved, never typed on a command line (a command file is a trust boundary and a strategy's
parameters are many and unbounded). It adds no way to arm: it asks the very port the tab asks, so the
registered-strategy check, the parameter validation, the symbol lease, the Spot rules, the position check and
the order session's opening are the tab's.

Order, so that a refusal changes nothing and says why:
  1. the venue is one this build trades on and this run serves;
  2. nothing is armed on it already (the tab only offers a venue with nothing armed);
  3. a saved arming exists (arm once from the desktop, or copy its state file, first);
  4. real money (decision O8): on a mainnet venue the operator typed the venue, because an armed strategy
     then places orders on its own;
  5. the port arms, and its refusal is told in the tab's words.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import STRATEGY_SUBJECT
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_identity import (
    venue_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.strategy.strategy_arm_words import (
    ARM_BLOCK_WORDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ArmStrategyForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    ArmedStrategyConfig,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.strategy_arm_result import (
    ArmStrategyBlockReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_strategy_controls import (
    VenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: The refusals the bots' own vocabulary already names; every other reason is a definition problem.
_REFUSAL_OF: dict[ArmStrategyBlockReason, BotRefusal] = {
    ArmStrategyBlockReason.SYMBOL_LEASED: BotRefusal.SYMBOL_LEASED,
    ArmStrategyBlockReason.SESSION_NOT_READY: BotRefusal.VENUE_NOT_READY,
}


class ArmStrategyForHostCommandHandler(
    ICommandHandler[ArmStrategyForHostCommand, BotCommandResult]
):
    def __init__(self, controls: IVenueStrategyControls) -> None:
        self._controls = controls

    def execute(self, command: ArmStrategyForHostCommand) -> BotCommandResult:
        venue = venue_of(command.venue)
        if not isinstance(venue, TradingVenue):
            return _refused(BotRefusal.INVALID_DEFINITION, venue)
        try:
            ports = self._controls.get(venue)
        except VenueNotEnabledError as not_served:
            return _refused(
                BotRefusal.VENUE_NOT_READY,
                f"this run does not serve {venue.value}, so no strategy can be armed on it "
                f"({not_served})",
            )
        problem = _problem_before_arming(ports)
        if problem is not None:
            return problem
        if venue.is_mainnet and command.confirmed_venue != venue.value:
            return _refused(
                BotRefusal.REAL_MONEY_NOT_CONFIRMED,
                f"An armed strategy places orders by itself with real money on {venue.display_name}: "
                f"arming it needs --confirm-venue {venue.value}",
            )
        saved = ports.arming.saved_selection()
        result = ports.arming.arm(saved)
        if result.armed:
            return BotCommandResult(
                accepted=True,
                bot_id=STRATEGY_SUBJECT,
                message=f"strategy armed on {venue.value}: {_words_of(saved)}",
            )
        reason = result.block_reason
        if reason is None:
            return _refused(
                BotRefusal.INVALID_DEFINITION,
                "Strategy could not be armed (no reason reported)",
            )
        detail = f" ({result.error_message})" if result.error_message else ""
        return _refused(
            _REFUSAL_OF.get(reason, BotRefusal.INVALID_DEFINITION),
            f"{ARM_BLOCK_WORDS[reason].rstrip('.')}{detail}",
        )


def _problem_before_arming(ports: VenueStrategyControls) -> BotCommandResult | None:
    armed = ports.armed.armed().config
    if armed is not None:
        return _refused(
            BotRefusal.INVALID_TRANSITION,
            f"a strategy is already armed on {ports.venue.value}: {_words_of(armed)}; "
            "disarm it first (`bot disarm-strategy`)",
        )
    if not ports.arming.saved_selection().strategy_key:
        return _refused(
            BotRefusal.INVALID_DEFINITION,
            f"no saved arming exists for {ports.venue.value}: the host arms the saved one and "
            "nothing is typed on the command line. Arm once from the desktop "
            "(Bots → Arm strategy…) first",
        )
    return None


def _words_of(config: ArmedStrategyConfig) -> str:
    """The saved arming in plain words (the tab's own summary needs the strategy catalogue's labels)."""
    parts = [
        f"{config.strategy_key} on {config.symbol} {config.interval}",
        f"{config.sizing_percent:g}% per order",
        f"{config.leverage:g}x",
    ]
    if config.strategy_params:
        parts.append(
            ", ".join(f"{k}={v}" for k, v in sorted(config.strategy_params.items()))
        )
    return ", ".join(parts)


def _refused(refusal: BotRefusal, words: str) -> BotCommandResult:
    return BotCommandResult.refused(
        refusal, f"{words}. Nothing was armed.", STRATEGY_SUBJECT
    )
