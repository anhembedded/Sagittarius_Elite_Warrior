"""`IOwnerPositionCheckpoints` as one JSON file per tag (`EPIC-039H`).

@details Written the way `JsonOwnerInventoryCheckpoints` writes: to a temporary file in the same
directory, flushed to disk, then `Path.replace()`d over the old one, so a crash leaves the previous
checkpoint whole. A file that cannot be read is reported and answered as no checkpoint: the position
is then derived again in full, which is always correct, only slower (and refused beyond the venue's
history window, as without a checkpoint).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.persistence.atomic_json_file import (
    write_json_atomically,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_position_checkpoints import (
    IOwnerPositionCheckpoints,
    OwnerPositionCheckpoint,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    OwnerPosition,
)

logger = logging.getLogger("App.Trading.PositionCheckpoints")

_SUFFIX = ".json"


class JsonOwnerPositionCheckpoints(IOwnerPositionCheckpoints):
    """Checkpoints as `<directory>/<tag>.json`."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def load(self, tag: str) -> OwnerPositionCheckpoint | None:
        path = self._path(tag)
        if not path.is_file():
            return None
        try:
            return _decode(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, ArithmeticError, KeyError, TypeError) as exc:
            logger.warning(
                "Position checkpoint %s is unreadable (%s); deriving in full.",
                path,
                exc,
            )
            return None

    def save(self, checkpoint: OwnerPositionCheckpoint) -> None:
        write_json_atomically(self._path(checkpoint.tag), _encode(checkpoint))
        logger.debug("Saved position checkpoint for %s", checkpoint.tag)

    def _path(self, tag: str) -> Path:
        return self._directory / f"{tag}{_SUFFIX}"


def _encode(checkpoint: OwnerPositionCheckpoint) -> dict[str, Any]:
    position = checkpoint.position
    return {
        "tag": checkpoint.tag,
        "run_started_at": checkpoint.run_started_at.isoformat(),
        "quantity": str(position.quantity),
        "average_entry": None
        if position.average_entry is None
        else str(position.average_entry),
        "realized_pnl": str(position.realized_pnl),
        "fees": str(position.fees),
        "last_trade_id": checkpoint.last_trade_id,
        "open_order_ids": sorted(checkpoint.open_order_ids),
        "read_from": checkpoint.read_from.isoformat(),
        "open_order_remaining": {
            str(order_id): str(owed)
            for order_id, owed in sorted(checkpoint.open_order_remaining.items())
        },
    }


def _decode(raw: dict[str, Any]) -> OwnerPositionCheckpoint:
    last_trade_id = raw["last_trade_id"]
    entry = raw["average_entry"]
    return OwnerPositionCheckpoint(
        tag=str(raw["tag"]),
        run_started_at=datetime.fromisoformat(raw["run_started_at"]),
        position=OwnerPosition(
            Decimal(raw["quantity"]),
            None if entry is None else Decimal(entry),
            Decimal(raw["realized_pnl"]),
            Decimal(raw["fees"]),
        ),
        last_trade_id=None if last_trade_id is None else int(last_trade_id),
        open_order_ids=frozenset(int(order_id) for order_id in raw["open_order_ids"]),
        read_from=datetime.fromisoformat(raw["read_from"]),
        open_order_remaining={
            int(order_id): Decimal(owed)
            for order_id, owed in raw.get("open_order_remaining", {}).items()
        },
    )
