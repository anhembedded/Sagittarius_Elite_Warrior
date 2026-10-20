"""`BOT-209` — the liquidation row's gap to the exit reads as a gap, on any symbol."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_liquidation import (
    liquidation_lines,
)


def _line(liquidation: str, exit_price: str, gap: str) -> str:
    verdict = Verdict(
        VerdictSeverity.OK,
        "LIQUIDATION_ESTIMATE",
        "estimate",
        {
            "liquidation_price": Decimal(liquidation),
            "exit_price": Decimal(exit_price),
            "gap": Decimal(gap),
        },
        subject="long",
    )
    return liquidation_lines((verdict,))[0].text


def test_a_gap_on_an_ordinary_symbol_reads_to_the_cent() -> None:
    text = _line("1586.8947", "2090.00", "503.1053")

    assert "503.11 before the exit at 2,090.00" in text


@pytest.mark.parametrize(
    ("gap", "shown"), [("0.0004", "0.0004"), ("0.00041234", "0.00041")]
)
def test_a_gap_on_a_sub_cent_symbol_is_never_written_as_zero(
    gap: str, shown: str
) -> None:
    text = _line("0.0036", "0.0040", gap)

    assert f"{shown} before the exit" in text
    assert " 0.00 before" not in text
