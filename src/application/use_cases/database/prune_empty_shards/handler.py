from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.database.prune_empty_shards.command import (
    PruneEmptyShardsCommand,
    PruneEmptyShardsResult,
)

logger = logging.getLogger("App.Database")


class PruneEmptyShardsCommandHandler(
    ICommandHandler[PruneEmptyShardsCommand, PruneEmptyShardsResult]
):
    """
    @brief Handler removing every shard with zero klines via IMarketDataRepository.
    """

    def __init__(self, repository: IMarketDataRepository) -> None:
        self._repository = repository

    def execute(self, command: PruneEmptyShardsCommand) -> PruneEmptyShardsResult:
        shards = self._repository.list_available_shards()
        removed: list[str] = []
        for symbol in shards:
            if command.cancellation_requested and command.cancellation_requested():
                logger.debug(
                    "[storage-vault] Prune cancelled after removing "
                    f"{len(removed)}/{len(shards)} empty shards."
                )
                break
            if self._repository.has_any_klines(symbol):
                continue
            self._repository.clear_klines(symbol, interval=None)
            removed.append(symbol)

        if removed:
            logger.info(
                f"[storage-vault] Pruned {len(removed)} empty shard(s) "
                f"(0 klines in any interval): {removed}"
            )
        else:
            logger.debug("[storage-vault] Prune found no empty shards.")

        return PruneEmptyShardsResult(
            removed_symbols=removed, scanned_count=len(shards)
        )
