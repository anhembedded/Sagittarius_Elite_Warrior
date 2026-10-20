"""`EPIC-026L` — the owner's figure: unset is off, set is exact, a typo is an error and never "off"."""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_figure import (
    LossCapFigure,
    LossCapFigureError,
    parse_loss_cap_figure,
)


@pytest.mark.parametrize("unset", [None, "", "   "])
def test_nothing_set_means_the_cap_is_off(unset: str | None) -> None:
    assert parse_loss_cap_figure(unset) is None


def test_an_amount_and_its_quote_asset_is_a_figure() -> None:
    figure = parse_loss_cap_figure(" 500 usdt ")
    assert figure == LossCapFigure(Decimal(500), "USDT")
    assert figure is not None and figure.text() == "500 USDT"


def test_a_decimal_amount_is_kept_exactly() -> None:
    figure = parse_loss_cap_figure("12.50 USDC")
    assert figure is not None and figure.amount == Decimal("12.50")


@pytest.mark.parametrize(
    "written",
    [
        "500",
        "USDT 500",
        "five hundred USDT",
        "-5 USDT",
        "0 USDT",
        "0.0 USDT",
        "500 USDT extra",
        500,
    ],
)
def test_a_set_figure_that_cannot_be_read_is_an_error_not_off(written: object) -> None:
    with pytest.raises(LossCapFigureError):
        parse_loss_cap_figure(written)


def test_a_bot_is_covered_when_its_symbol_ends_in_the_quote_asset() -> None:
    figure = LossCapFigure(Decimal(500), "USDT")
    assert figure.covers("BTCUSDT")
    assert not figure.covers("BTCUSDC")
    assert not figure.covers("USDTBTC")
