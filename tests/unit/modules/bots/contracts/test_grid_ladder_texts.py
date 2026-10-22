"""`BOT-193` - the words of the ladder: what each figure is, and what it is not.

@details The wording is checked as a person reads it: a figure the record cannot give is said so
and never written as zero; profit is before fees until the rate is known; grid profit is net of
both legs' fees and leaves Futures funding out; and no line promises how often price crosses a
level or a profit per day (`domain-truth-rule.md`).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.number_text import percent_text
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import (
    LadderSummary,
    PriceMark,
    PricePosition,
    RecordedCycles,
    TriggerMark,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder_texts import (
    FEE_NOT_SAVED,
    LIQUIDATION_NOT_SAVED,
    NOT_ESTIMATED,
    RATE_SOURCE,
    age_text,
    brief_summary_line,
    cycle_profit_text,
    net_figures_note,
    percent_of,
    position_texts,
    recorded_average_text,
    signed_percent_of,
    small_money_text,
    step_text,
    summary_line,
    waiting_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    NO_PRICE_YET,
    NO_VALUE,
    plain_money,
    plain_price,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridSpacing,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import write_value
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind


def _summary(**fields: object) -> LadderSummary:
    values: dict[str, object] = {
        "spacing": GridSpacing.ARITHMETIC,
        "smallest_step_fraction": Decimal("0.0143"),
        "largest_step_fraction": Decimal("0.0167"),
        "maker_fee": None,
        "average_cycle_quote": Decimal("8.5"),
    }
    return LadderSummary(**{**values, **fields})  # type: ignore[arg-type]


def _position(**fields: object) -> PricePosition:
    values: dict[str, object] = {
        "last_price": Decimal(64000),
        "age_seconds": 300,
        "lower": PriceMark(Decimal(60000), Decimal("-0.0625")),
        "upper": PriceMark(Decimal(70000), Decimal("0.09375")),
        "stop_loss": PriceMark(Decimal(57000), Decimal("-0.109375")),
        "take_profit": None,
        "has_liquidation_price": False,
    }
    return PricePosition(**{**values, **fields})  # type: ignore[arg-type]


def test_an_arithmetic_summary_says_the_bottom_grid_is_the_widest() -> None:
    line = summary_line(_summary(), plain_money)

    assert line.startswith(
        "Arithmetic spacing: steps from 1.43% at the top to 1.67% at the bottom"
    )


def test_a_geometric_summary_says_every_grid_steps_the_same() -> None:
    line = summary_line(
        _summary(
            spacing=GridSpacing.GEOMETRIC, largest_step_fraction=Decimal("0.0143")
        ),
        plain_money,
    )

    assert line.startswith("Geometric spacing: every grid steps 1.43%")


def test_a_summary_without_the_fee_says_the_profit_is_before_fees_and_why() -> None:
    line = summary_line(_summary(), plain_money)

    assert "about 8.50 per cycle" in line
    assert FEE_NOT_SAVED in line
    assert "(estimate)" in line


def test_a_summary_with_the_fee_names_it_for_both_legs() -> None:
    line = summary_line(_summary(maker_fee=Decimal("0.001")), plain_money)

    assert "after the 0.10% maker fee on both legs" in line
    assert FEE_NOT_SAVED not in line


def test_an_unsized_cycle_is_not_estimated_rather_than_zero() -> None:
    line = summary_line(_summary(average_cycle_quote=None), plain_money)

    assert "not estimated" in line
    assert "0.00" not in line


def test_the_brief_summary_keeps_the_figures_and_drops_the_reasons() -> None:
    brief = brief_summary_line(_summary(), plain_money)

    assert brief == (
        "Arithmetic spacing, 1.43% to 1.67%; about 8.50 before fees (estimate)"
    )
    assert FEE_NOT_SAVED not in brief
    assert brief_summary_line(
        _summary(spacing=GridSpacing.GEOMETRIC), plain_money
    ).startswith("Geometric spacing, 1.43% each")


def test_a_row_says_the_steps_in_a_few_words() -> None:
    assert step_text(_summary()) == "1.43% to 1.67%"
    assert step_text(_summary(spacing=GridSpacing.GEOMETRIC)) == "1.43% each"
    assert step_text(_summary(largest_step_fraction=Decimal("0.0143"))) == "1.43% each"


def test_a_row_says_the_cycle_profit_before_fees_until_the_fee_is_known() -> None:
    assert cycle_profit_text(_summary(), plain_money) == ("about 8.50 before fees")
    assert cycle_profit_text(_summary(maker_fee=Decimal("0.001")), plain_money) == (
        "about 8.50 after fees (run-start rate)"
    )
    assert (
        cycle_profit_text(_summary(average_cycle_quote=None), plain_money)
        == NOT_ESTIMATED
    )


def test_the_recorded_average_is_the_profit_the_cycles_booked_over_them() -> None:
    assert recorded_average_text(RecordedCycles(6, Decimal(30)), plain_money) == "5.00"


def test_no_completed_cycle_has_no_recorded_average() -> None:
    assert recorded_average_text(RecordedCycles(0, Decimal(0)), plain_money) == NO_VALUE
    assert recorded_average_text(RecordedCycles(0, None), plain_money) == NO_VALUE


def test_the_position_texts_give_the_price_its_age_the_edges_and_the_exits() -> None:
    texts = position_texts(_position(), plain_price)

    assert texts.last_price == "64,000.00, 5 min ago"
    assert texts.lower_edge == "60,000.00 (-6.25%)"
    assert texts.upper_edge == "70,000.00 (+9.38%)"
    assert texts.stop_loss == "57,000.00 (-10.94%)"
    assert texts.take_profit == "off"
    assert texts.liquidation is None


def test_no_price_heard_says_no_price_yet_and_gives_no_distances() -> None:
    texts = position_texts(
        _position(
            last_price=None,
            age_seconds=None,
            lower=PriceMark(Decimal(60000), None),
            upper=PriceMark(Decimal(70000), None),
            stop_loss=PriceMark(Decimal(57000), None),
        ),
        plain_price,
    )

    assert texts.last_price == NO_PRICE_YET
    assert texts.lower_edge == "60,000.00"
    assert texts.stop_loss == "57,000.00"


def test_a_price_without_its_moment_gives_no_age() -> None:
    assert position_texts(_position(age_seconds=None), plain_price).last_price == (
        "64,000.00"
    )


def test_a_position_venue_says_its_liquidation_price_is_not_in_the_record() -> None:
    texts = position_texts(_position(has_liquidation_price=True), plain_price)

    assert texts.liquidation == LIQUIDATION_NOT_SAVED
    assert position_texts(_position(), plain_price).liquidation is None


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (0, "0 s ago"),
        (59, "59 s ago"),
        (60, "1 min ago"),
        (3599, "59 min ago"),
        (3600, "1 h ago"),
        (86_399, "23 h ago"),
        (86_400, "1 d ago"),
    ],
)
def test_an_age_is_written_in_the_largest_unit_it_fills(
    seconds: int, text: str
) -> None:
    assert age_text(seconds) == text


@pytest.mark.parametrize(
    ("fraction", "text"),
    [("0.0125", "+1.25%"), ("-0.05", "-5.00%"), ("0", "0.00%"), ("-0.00001", "0.00%")],
)
def test_a_signed_percent_carries_its_sign_and_never_negative_zero(
    fraction: str, text: str
) -> None:
    assert signed_percent_of(Decimal(fraction)) == text


@pytest.mark.parametrize("value", [0.0, 0.5, 1.43, 12.5, 1234.567, 100.0])
def test_percent_text_writes_what_the_tabs_formatter_writes(value: float) -> None:
    assert percent_text(value) == write_value(ColumnKind.PERCENT, value)


def test_a_fraction_is_written_as_per_cent() -> None:
    assert percent_of(Decimal("0.0143")) == "1.43%"


def test_no_text_promises_a_crossing_rate_or_a_profit_per_day() -> None:
    summary = _summary(maker_fee=Decimal("0.001"))
    texts = position_texts(_position(has_liquidation_price=True), plain_price)
    lines = (
        summary_line(summary, plain_money),
        step_text(summary),
        cycle_profit_text(summary, plain_money),
        recorded_average_text(RecordedCycles(6, Decimal(30)), plain_money),
        texts.last_price,
        texts.liquidation or "",
    )

    text = " ".join(lines).lower()
    for promise in ("per day", "daily", "/day", "apr", "per hour", "will cross"):
        assert promise not in text


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ("0.000192", "less than 0.01"),
        ("0.004", "less than 0.01"),
        ("-0.004", "more than -0.01"),
        ("0.005", "0.01"),
        ("0", "0.00"),
        ("-0.01", "-0.01"),
        ("12.5", "12.50"),
    ],
)
def test_a_nonzero_amount_that_rounds_to_zero_is_said_to_be_small(
    value: str, text: str
) -> None:
    assert small_money_text(Decimal(value), plain_money) == text


def test_a_sub_cent_cycle_profit_and_average_are_never_written_as_zero() -> None:
    summary = _summary(average_cycle_quote=Decimal("0.000192"))

    assert "less than 0.01" in summary_line(summary, plain_money)
    assert cycle_profit_text(summary, plain_money) == "less than 0.01 before fees"
    assert (
        recorded_average_text(RecordedCycles(3, Decimal("0.012")), plain_money)
        == "less than 0.01"
    )


def test_an_unsized_brief_summary_does_not_call_a_missing_figure_an_estimate() -> None:
    brief = brief_summary_line(_summary(average_cycle_quote=None), plain_money)

    assert brief.endswith("not estimated")
    assert "(estimate)" not in brief


def test_a_net_figure_says_which_rate_it_uses_wherever_it_is_shown() -> None:
    """`BOT-194` - the recorded rate is the run's start, never presented as today's."""
    summary = _summary(maker_fee=Decimal("0.0002"))

    assert RATE_SOURCE in cycle_profit_text(summary, plain_money)
    assert RATE_SOURCE in brief_summary_line(summary, plain_money)
    assert "rate recorded at run start" in summary_line(summary, plain_money)
    note = net_figures_note(summary)
    assert "0.02% maker rate recorded when this run started, not today's rate" in note


def test_without_a_recorded_rate_the_note_says_the_net_is_blank_and_why() -> None:
    note = net_figures_note(_summary())

    assert note.startswith("Net figures are blank")
    assert FEE_NOT_SAVED in note
    assert RATE_SOURCE not in cycle_profit_text(_summary(), plain_money)


def test_a_bot_waiting_on_its_range_alone_names_the_range() -> None:
    text = waiting_text(_position(last_price=Decimal(58000)), plain_price)

    assert text.startswith("Waiting for the price to enter 60,000.00–70,000.00")


def test_a_long_waiting_on_its_trigger_names_the_trigger_and_the_better_side() -> None:
    """`EPIC-046B`, ADR 046 D5: "Waiting for the price ≤ X (now Y)"."""
    trigger = TriggerMark(PriceMark(Decimal(62000), None), at_or_below=True)

    text = waiting_text(_position(trigger=trigger), plain_price)

    assert text.startswith(
        "Waiting for the price ≤ 62,000.00 within 60,000.00–70,000.00"
    )
    assert "last price 64,000.00" in text
    assert text.endswith("nothing is placed until it is")


def test_a_short_waiting_on_its_trigger_wants_the_price_at_or_above_it() -> None:
    trigger = TriggerMark(PriceMark(Decimal(66000), None), at_or_below=False)

    text = waiting_text(_position(trigger=trigger), plain_price)

    assert text.startswith("Waiting for the price ≥ 66,000.00")


def test_a_trigger_wait_before_any_price_says_none_was_heard() -> None:
    trigger = TriggerMark(PriceMark(Decimal(62000), None), at_or_below=True)

    text = waiting_text(_position(trigger=trigger, last_price=None), plain_price)

    assert "no price heard yet" in text
