"""`IOwnerInventoryCheckpoints` as one JSON file per tag (`EPIC-029` D6).

@details Written the way `JsonBotStore` writes a bot: to a temporary file in
the same directory, flushed to disk, then `Path.replace()`d over the old
one, so a crash leaves the previous checkpoint whole. A file that cannot be
read is reported and answered as no checkpoint: the inventory is then
derived again in full, which is always correct, only slower.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_inventory_checkpoints import (
    IOwnerInventoryCheckpoints,
    OwnerInventoryCheckpoint,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

logger = logging.getLogger("App.Trading.InventoryCheckpoints")

_SUFFIX = ".json"
_TEMP_SUFFIX = ".json.tmp"


class JsonOwnerInventoryCheckpoints(IOwnerInventoryCheckpoints):
    """Checkpoints as `<directory>/<tag>.json`."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def load(self, tag: str) -> OwnerInventoryCheckpoint | None:
        path = self._path(tag)
        if not path.is_file():
            return None
        try:
            return _decode(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, ArithmeticError, KeyError, TypeError) as exc:
            logger.warning(
                "Inventory checkpoint %s is unreadable (%s); deriving in full.",
                path,
                exc,
            )
            return None

    def save(self, checkpoint: OwnerInventoryCheckpoint) -> None:
        text = json.dumps(_encode(checkpoint), indent=2, sort_keys=True)
        self._directory.mkdir(parents=True, exist_ok=True)
        target = self._path(checkpoint.tag)
        temp_path = target.with_suffix(_TEMP_SUFFIX)
        try:
            with temp_path.open("w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            temp_path.replace(target)
        finally:
            temp_path.unlink(missing_ok=True)
        logger.debug("Saved inventory checkpoint for %s", checkpoint.tag)

    def _path(self, tag: str) -> Path:
        return self._directory / f"{tag}{_SUFFIX}"


def _encode(checkpoint: OwnerInventoryCheckpoint) -> dict[str, Any]:
    return {
        "tag": checkpoint.tag,
        "run_started_at": checkpoint.run_started_at.isoformat(),
        "quantity": str(checkpoint.inventory.quantity),
        "cost": str(checkpoint.inventory.cost),
        "last_trade_id": checkpoint.last_trade_id,
        "open_order_ids": sorted(checkpoint.open_order_ids),
        "read_from": checkpoint.read_from.isoformat(),
    }


def _decode(raw: dict[str, Any]) -> OwnerInventoryCheckpoint:
    last_trade_id = raw["last_trade_id"]
    return OwnerInventoryCheckpoint(
        tag=str(raw["tag"]),
        run_started_at=datetime.fromisoformat(raw["run_started_at"]),
        inventory=OwnerInventory(Decimal(raw["quantity"]), Decimal(raw["cost"])),
        last_trade_id=None if last_trade_id is None else int(last_trade_id),
        open_order_ids=frozenset(int(order_id) for order_id in raw["open_order_ids"]),
        read_from=datetime.fromisoformat(raw["read_from"]),
    )
