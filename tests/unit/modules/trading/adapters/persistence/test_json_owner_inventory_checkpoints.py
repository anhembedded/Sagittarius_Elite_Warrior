"""`JsonOwnerInventoryCheckpoints` keeps a checkpoint whole, or none."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.persistence.json_owner_inventory_checkpoints import (
    JsonOwnerInventoryCheckpoints,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_inventory_checkpoints import (
    OwnerInventoryCheckpoint,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

_CHECKPOINT = OwnerInventoryCheckpoint(
    tag="a3f9c1",
    run_started_at=datetime(2026, 10, 1, tzinfo=UTC),
    inventory=OwnerInventory(Decimal("0.001998"), Decimal("99.95")),
    last_trade_id=42,
    open_order_ids=frozenset({7, 3}),
    read_from=datetime(2026, 10, 3, 11, 59, tzinfo=UTC),
)


def test_a_saved_checkpoint_reads_back_equal(tmp_path: Path) -> None:
    store = JsonOwnerInventoryCheckpoints(tmp_path / "checkpoints")
    store.save(_CHECKPOINT)

    assert JsonOwnerInventoryCheckpoints(tmp_path / "checkpoints").load("a3f9c1") == (
        _CHECKPOINT
    )


def test_a_tag_with_no_checkpoint_has_none(tmp_path: Path) -> None:
    assert JsonOwnerInventoryCheckpoints(tmp_path).load("b00000") is None


def test_an_unreadable_checkpoint_is_none_so_the_inventory_is_derived_in_full(
    tmp_path: Path,
) -> None:
    (tmp_path / "a3f9c1.json").write_text('{"tag": "a3f9c1", "quantity": "x"}')
    assert JsonOwnerInventoryCheckpoints(tmp_path).load("a3f9c1") is None


def test_a_checkpoint_with_no_fill_yet_round_trips(tmp_path: Path) -> None:
    empty = OwnerInventoryCheckpoint(
        tag="a3f9c1",
        run_started_at=_CHECKPOINT.run_started_at,
        inventory=OwnerInventory(Decimal(0), Decimal(0)),
        last_trade_id=None,
        open_order_ids=frozenset(),
        read_from=_CHECKPOINT.run_started_at,
    )
    store = JsonOwnerInventoryCheckpoints(tmp_path)
    store.save(empty)
    assert store.load("a3f9c1") == empty
