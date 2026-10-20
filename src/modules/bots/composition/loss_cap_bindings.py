"""The account-level loss cap's own state and wiring (`EPIC-026L`).

Singletons: the cap holds the record every reader of its status and every start asks about, so
two instances would disagree about whether it is tripped. `ILossCapHold` (asked by the runner) and
`ILossCapStatus` (asked by the health section) are the one `AccountLossCap`.

@par Where the record goes
`<bots state folder>/../loss_cap.json`, beside the bots' folder and not in it, as `bot_plan.json`
is: a file inside the folder would be read as a bot.

@par The figure
`bots.account_loss_cap` (`ConfigKeys.BOTS_ACCOUNT_LOSS_CAP`), read when the cap is first asked
for. A figure that is set and unreadable raises `LossCapFigureError` there, so a host never runs
with a cap the owner thinks is on and is not.
"""

from __future__ import annotations

import logging
from pathlib import Path

from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.file_loss_cap_store import (
    FileLossCapStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_status_report import (
    BotsStateDirectory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.account_loss_cap import (
    AccountLossCap,
    LossCapParts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.loss_cap_sampler import (
    LossCapSampler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.loss_cap.loss_cap_stopper import (
    LossCapStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_acknowledgement import (
    ILossCapAcknowledgement,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_hold import (
    ILossCapHold,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_status import (
    ILossCapStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_store import (
    ILossCapStore,
    LossCapRecordUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_figure import (
    parse_loss_cap_figure,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_ledger import (
    LossCapLedger,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_policy import (
    LossCapRecord,
    LossCapTrip,
    LossCapTripReason,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer

logger = logging.getLogger("App.Bots.LossCap")

RECORD_FILE_NAME = "loss_cap.json"


def loss_cap_record_path(state_directory: Path) -> Path:
    return state_directory.parent / RECORD_FILE_NAME


def bind_loss_cap(container: IContainer) -> None:
    container.singleton(ILossCapStore, _build_store)
    container.singleton(AccountLossCap, _build_cap)
    container.singleton(ILossCapHold, lambda c: c.resolve(AccountLossCap))
    container.singleton(ILossCapStatus, lambda c: c.resolve(AccountLossCap))
    container.singleton(ILossCapAcknowledgement, lambda c: c.resolve(AccountLossCap))


def _build_store(container: IContainer) -> ILossCapStore:
    return FileLossCapStore(
        loss_cap_record_path(container.resolve(BotsStateDirectory).path)
    )


def _build_cap(container: IContainer) -> AccountLossCap:
    figure = parse_loss_cap_figure(
        container.resolve(IConfig).get(ConfigKeys.BOTS_ACCOUNT_LOSS_CAP.value)
    )
    clock = container.resolve(IBotClock)
    store = container.resolve(ILossCapStore)
    parts = LossCapParts(
        LossCapSampler(container.resolve(ICommandDispatcher), figure),
        LossCapStopper(container.resolve(ICommandDispatcher)),
        store,
        container.resolve(IEventPublisher),
        clock,
    )
    try:
        record = store.read()
    except LossCapRecordUnreadableError as unreadable:
        now = clock.now()
        logger.critical(
            "[loss-cap] %s; the cap starts TRIPPED until you acknowledge it", unreadable
        )
        trip = LossCapTrip(
            LossCapTripReason.RECORD_UNREADABLE,
            now,
            now.date(),
            None,
            "" if figure is None else figure.text(),
            f"{unreadable}",
        )
        return AccountLossCap(
            parts,
            figure,
            LossCapRecord(LossCapLedger.empty(now.date()), trip),
            announce_restored_trip=True,
        )
    restored = record or LossCapRecord(LossCapLedger.empty(clock.now().date()))
    if restored.trip is not None:
        logger.warning(
            "[loss-cap] restored TRIPPED (%s): no bot starts until you acknowledge it",
            restored.trip.detail,
        )
    return AccountLossCap(parts, figure, restored)
