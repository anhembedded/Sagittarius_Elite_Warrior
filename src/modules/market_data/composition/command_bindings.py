"""market_data's write side: the nine commands and their handlers.

The Engine's `ICommandDispatcher` routes a command *object* to the handler bound
against its type, so this table is the routing table — a command with no entry
here fails at dispatch time, not at import time, which is why the list lives in
one readable place rather than beside each handler.

`bind` (transient), never `singleton`: a handler holds the state of the one
operation it is running — a sync's progress, a stream's subscription — and two
concurrent syncs must not share it. The state that *is* shared sits behind
`InFlightSyncGuard`, which `adapter_bindings.py` registers as a singleton
precisely because it is the exception.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.clear_market_data import (
    ClearMarketDataCommand,
    ClearMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.export_market_data import (
    ExportMarketDataCommand,
    ExportMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.import_market_data import (
    ImportMarketDataCommand,
    ImportMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.prune_empty_shards import (
    PruneEmptyShardsCommand,
    PruneEmptyShardsCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.repair_data_gap import (
    RepairDataGapCommand,
    RepairDataGapCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream import (
    StartLiveStreamCommand,
    StartLiveStreamCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream import (
    StopLiveStreamCommand,
    StopLiveStreamCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.bulk_sync_market_data import (
    BulkSyncMarketDataCommand,
    BulkSyncMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.sync_market_data import (
    SyncMarketDataCommand,
    SyncMarketDataCommandHandler,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_commands(container: IContainer) -> None:
    """Route each market_data command type to the handler that executes it."""
    container.bind(SyncMarketDataCommand, SyncMarketDataCommandHandler)
    container.bind(BulkSyncMarketDataCommand, BulkSyncMarketDataCommandHandler)
    container.bind(StartLiveStreamCommand, StartLiveStreamCommandHandler)
    container.bind(StopLiveStreamCommand, StopLiveStreamCommandHandler)
    container.bind(ClearMarketDataCommand, ClearMarketDataCommandHandler)
    container.bind(RepairDataGapCommand, RepairDataGapCommandHandler)
    container.bind(PruneEmptyShardsCommand, PruneEmptyShardsCommandHandler)
    container.bind(ExportMarketDataCommand, ExportMarketDataCommandHandler)
    container.bind(ImportMarketDataCommand, ImportMarketDataCommandHandler)
