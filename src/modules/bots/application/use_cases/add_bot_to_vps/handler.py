"""`EPIC-047E` — handler for `AddBotToVpsCommand`: the bot's definition as an `add` request to the VPS host.

The definition is the one Export plan… writes (`ExportBotPlanQuery`), so a bot reaches the host with the same name,
kind, venue, symbol and parameters a plan file would carry; the host's `add` creates a DRAFT (the entry carries
no state): Add to VPS starts nothing, places no order and asks no real-money question (the host's Start
asks it, typed, when the owner starts the bot there). The host judges the entry again after the wire (kind, venue,
parameters, a name already taken) and answers in its own words; this handler tells them, it adds none of its own rule.

A request is sent once. A reply that never came is `unknown`, never "not added" (the host may have created the bot).
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    ADD_SUBJECT,
    HostControlAction,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    BotPlanDocument,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.plan_export import (
    UnknownBotsError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.export_bot_plan import (
    ExportBotPlanQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.add_bot_to_vps.command import (
    AddBotToVpsCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.add_bot_to_vps.result import (
    AddedToVps,
    AddToVpsResult,
    NotAddedToVps,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_vps_delivery import (
    IVpsDelivery,
)

#: How long the host has to record its answer to an add (the `bot add` verb waits as long).
REPLY_WAIT_S = 20.0
GONE_WORDS = "That bot no longer exists here, so nothing was sent."


class AddBotToVpsCommandHandler(ICommandHandler[AddBotToVpsCommand, AddToVpsResult]):
    def __init__(self, dispatcher: ICommandDispatcher, delivery: IVpsDelivery) -> None:
        self._dispatcher = dispatcher
        self._delivery = delivery

    def execute(self, command: AddBotToVpsCommand) -> AddToVpsResult:
        try:
            document = cast(
                BotPlanDocument,
                self._dispatcher.dispatch(
                    ExportBotPlanQuery,
                    ExportBotPlanQuery((command.bot_id,), all_stopped=True),
                ),
            )
        except UnknownBotsError:
            return NotAddedToVps(command.bot_id, GONE_WORDS)
        planned = document.bots[0]
        try:
            entry = NewBotEntry(
                planned.name,
                planned.kind,
                planned.venue.identifier,
                planned.symbol,
                tuple(ParameterSetting(k, v) for k, v in planned.params.items()),
            )
        except ValueError as invalid:
            return NotAddedToVps(
                planned.name, f"The bot cannot be sent as it is: {invalid}."
            )
        reply = self._delivery.send(
            HostControlRequest(HostControlAction.ADD, ADD_SUBJECT, entry=entry),
            REPLY_WAIT_S,
        )
        if reply.status is HostControlStatus.DONE:
            return AddedToVps(planned.name, reply.bot_id, reply.message)
        return NotAddedToVps(
            planned.name,
            reply.message,
            unknown=reply.status is HostControlStatus.NO_ANSWER,
        )
