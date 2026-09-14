from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class SingleSyncProgressEvent(BaseEvent):
    """
    @brief Emitted to report the progress of a single synchronization process.

    @details BOT-122: more than one screen listens to this event on the same
    bus (Backtest and Data Management both fan it through `SyncProgressFeed`),
    and `SyncMarketDataCommandHandler` is the one choke point every sync
    dispatch — Backtest, Data Management's single sync, and each target of
    Data Management's bulk sync — passes through (`BOT-121`). `symbol`/
    `interval` alone cannot tell a listener "is this event mine": two
    different actions can legitimately target the same symbol+interval (a
    Backtest coverage-gap sync and a Data Management manual resync racing
    for BTCUSDT/1m), and matching on them is a business-data coincidence,
    not an identity. `correlation_id` — copied straight from the
    `SyncMarketDataCommand`/`BulkSyncMarketDataCommand` that caused this
    event — IS that identity: a listener sets its own value when it
    dispatches, keeps it, and only accepts a report whose `correlation_id`
    matches. See `SyncMarketDataCommand.correlation_id` for where it comes
    from.
    """

    symbol: str
    interval: str
    current: int
    total: int
    correlation_id: str = ""
