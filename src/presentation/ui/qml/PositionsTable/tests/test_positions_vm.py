# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_vm import (
    PositionsVM,
)


def _position(
    symbol="BTCUSDT", amt="0.5", pnl="10.0", leverage=10, liquidation_price=None
) -> LivePosition:
    return LivePosition(
        symbol=symbol,
        position_amt=Decimal(amt),
        entry_price=Decimal("64000.00"),
        mark_price=Decimal("64500.00"),
        unrealized_pnl=Decimal(pnl),
        leverage=leverage,
        margin_type=MarginType.CROSSED,
        liquidation_price=liquidation_price,
        updated_at=datetime.now(UTC),
    )


def _vm() -> PositionsVM:
    return PositionsVM()


def test_starts_empty() -> None:
    assert _vm().rows == []


def test_set_rows_projects_every_field() -> None:
    vm = _vm()
    vm.set_rows([build_position_row(_position())])

    (row,) = vm.rows
    assert row["symbol"] == "BTCUSDT"
    assert row["sideLabel"] == "LONG"
    assert row["sideIsLong"] is True
    assert row["sizeText"] == "0.5000"
    assert row["entryText"] == "64,000.00"
    assert row["markText"] == "64,500.00"
    assert row["pnlText"] == "+10.00 USDT"
    assert row["leverageText"] == "10x"
    assert row["liquidationText"] == "—"


def test_a_reported_liquidation_price_renders_formatted() -> None:
    vm = _vm()
    vm.set_rows([build_position_row(_position(liquidation_price=Decimal("32140.00")))])

    assert vm.rows[0]["liquidationText"] == "32,140.00"


def test_short_position_and_negative_pnl_use_the_bear_colour() -> None:
    vm = _vm()
    vm.set_rows([build_position_row(_position(amt="-0.5", pnl="-10.0"))])

    (row,) = vm.rows
    assert row["sideLabel"] == "SHORT"
    assert row["sideIsLong"] is False
    assert row["pnlColor"] != ""
    # Distinct colours for profit vs loss — not the same literal.
    profit_row = PositionsVM()
    profit_row.set_rows([build_position_row(_position(amt="0.5", pnl="10.0"))])
    assert row["pnlColor"] != profit_row.rows[0]["pnlColor"]


def test_set_rows_replaces_the_previous_set() -> None:
    vm = _vm()
    vm.set_rows([build_position_row(_position(symbol="BTCUSDT"))])
    vm.set_rows([build_position_row(_position(symbol="ETHUSDT"))])

    assert len(vm.rows) == 1
    assert vm.rows[0]["symbol"] == "ETHUSDT"


def test_build_position_row_reads_side_from_the_signed_amount() -> None:
    assert build_position_row(_position(amt="1.0")).side is PositionSide.LONG
    assert build_position_row(_position(amt="-1.0")).side is PositionSide.SHORT
