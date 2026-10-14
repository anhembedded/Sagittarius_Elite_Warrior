"""`JsonOwnerPositionCheckpoints` keeps a checkpoint whole, or none (`EPIC-039H`)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.persistence.json_owner_position_checkpoints import (
    JsonOwnerPositionCheckpoints,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_owner_position_checkpoints import (
    OwnerPositionCheckpoint,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    EMPTY_POSITION,
    OwnerPosition,
)

_CHECKPOINT = OwnerPositionCheckpoint(
    tag="f0a1b2",
    run_started_at=datetime(2026, 10, 1, tzinfo=UTC),
    position=OwnerPosition(
        Decimal("-0.0125"), Decimal("64000.5"), Decimal("12.34"), Decimal("0.77")
    ),
    last_trade_id=42,
    open_order_ids=frozenset({7, 3}),
    read_from=datetime(2026, 10, 3, 11, 59, tzinfo=UTC),
)


def test_a_saved_checkpoint_reads_back_equal(tmp_path: Path) -> None:
    JsonOwnerPositionCheckpoints(tmp_path / "checkpoints").save(_CHECKPOINT)

    assert JsonOwnerPositionCheckpoints(tmp_path / "checkpoints").load("f0a1b2") == (
        _CHECKPOINT
    )


def test_a_tag_with_no_checkpoint_has_none(tmp_path: Path) -> None:
    assert JsonOwnerPositionCheckpoints(tmp_path).load("b00000") is None


def test_an_unreadable_checkpoint_is_none_so_the_position_is_derived_in_full(
    tmp_path: Path,
) -> None:
    (tmp_path / "f0a1b2.json").write_text('{"tag": "f0a1b2", "quantity": "x"}')

    assert JsonOwnerPositionCheckpoints(tmp_path).load("f0a1b2") is None


def test_a_flat_checkpoint_with_no_fill_yet_round_trips(tmp_path: Path) -> None:
    flat = OwnerPositionCheckpoint(
        tag="f0a1b2",
        run_started_at=_CHECKPOINT.run_started_at,
        position=EMPTY_POSITION,
        last_trade_id=None,
        open_order_ids=frozenset(),
        read_from=_CHECKPOINT.run_started_at,
    )
    store = JsonOwnerPositionCheckpoints(tmp_path)

    store.save(flat)

    assert store.load("f0a1b2") == flat
