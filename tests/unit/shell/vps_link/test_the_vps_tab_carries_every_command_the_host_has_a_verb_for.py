"""`EPIC-047E` (AC3) - every Bots tab command that has a host verb is carried to the host by the VPS tab, as that verb.

The parity table of `EPIC-045D` says which `bot` verb each command of the Bots tab reaches on the running host. The VPS tab
sends the same commands through the same door, so each row with a verb must translate to the verb's action. A command
added to the table without a builder here fails, so the VPS tab cannot silently drop a new way to change a bot.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.remote_host.remote_requests import (
    request_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue import (
    ChangeBotVenueCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot import (
    DeleteBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot import (
    PauseBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.architecture.bots_tab_host_parity_rows import (
    PARITY,
    HostVerb,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_bots import (
    minimal_bot,
)

BOT = replace(minimal_bot(), config={"grid_count": "5"})
ID = BOT.bot_id

#: One command of each class the parity table names, built so the translation has something to carry.
BUILDERS: dict[str, Callable[[], object]] = {
    "CreateBotCommand": lambda: CreateBotCommand(
        "n", "grid", TradingVenue.SPOT_TESTNET, "BTCUSDT", {"grid_count": "5"}
    ),
    "EditBotCommand": lambda: EditBotCommand(ID, BOT.name, {"grid_count": "6"}),
    "StartBotCommand": lambda: StartBotCommand(ID),
    "PauseBotCommand": lambda: PauseBotCommand(ID),
    "ResumeBotCommand": lambda: ResumeBotCommand(ID),
    "StopBotCommand": lambda: StopBotCommand(ID, ExposureHandling.KEEP),
    "DeleteBotCommand": lambda: DeleteBotCommand(ID),
    "ConfirmBotResumeCommand": lambda: ConfirmBotResumeCommand(ID, "0a1b2c3d"),
    "ChangeBotVenueCommand": lambda: ChangeBotVenueCommand(
        ID, TradingVenue.SPOT_MAINNET
    ),
}

CARRIED = sorted(name for name, row in PARITY.items() if isinstance(row, HostVerb))


def test_every_command_with_a_host_verb_has_a_builder_here() -> None:
    assert sorted(BUILDERS) == CARRIED


@pytest.mark.parametrize("name", CARRIED)
def test_the_vps_tab_sends_the_verbs_action(name: str) -> None:
    row = PARITY[name]
    assert isinstance(row, HostVerb)

    sent = request_of(BUILDERS[name](), {ID: BOT})

    assert isinstance(sent, HostControlRequest)
    assert sent.action is row.action
    assert isinstance(sent.action, HostControlAction)
