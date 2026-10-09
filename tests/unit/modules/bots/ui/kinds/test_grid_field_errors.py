"""`EPIC-034F` — a verdict shows on the field it is about, and every
constraint decides where."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.exchange_rules import (
    CAPITAL_FIELD,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_constraints import (
    GRID_CONSTRAINTS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_field_errors import (
    ADVICE,
    BLOCKS,
    FIELDS_OF_CODE,
    NO_FIELD,
    field_errors,
    field_of_code,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)

_CONFIG_KEYS = {
    "lower",
    "upper",
    "grid_count",
    "spacing",
    "capital_quote",
    "stop_loss",
    "take_profit",
}


def _verdict(code: str, severity: VerdictSeverity, reason: str = "r") -> Verdict:
    return Verdict(severity, code, reason, {"n": Decimal(1)})


def test_every_violation_code_either_has_a_field_or_says_why_not() -> None:
    codes = {code for c in GRID_CONSTRAINTS for code in c.violations}
    codes |= {"PARAMETERS_NOT_SET", "PARAMETERS_UNREADABLE"}
    # The balance is judged on the exchange's snapshot (`BOT-174`) and speaks
    # on the Capital field through `field_verdicts`.
    codes |= {CAPITAL_FIELD}
    assert codes == set(FIELDS_OF_CODE) | set(NO_FIELD)
    assert not set(FIELDS_OF_CODE) & set(NO_FIELD)


def test_every_field_named_is_a_parameter_of_the_grid() -> None:
    assert {f for fields in FIELDS_OF_CODE.values() for f in fields} <= _CONFIG_KEYS


def test_a_blocking_verdict_says_it_blocks_and_advice_says_it_is_advice() -> None:
    shown = field_errors(
        [
            _verdict("CAPITAL_ABOVE_BALANCE", VerdictSeverity.REFUSED, "too much"),
            _verdict("ARITHMETIC_ON_WIDE_RANGE", VerdictSeverity.WARNING, "thin"),
        ]
    )
    assert shown["capital_quote"].text == f"{BLOCKS}too much"
    assert shown["capital_quote"].blocks
    assert shown["spacing"].text == f"{ADVICE}thin"
    assert not shown["spacing"].blocks


def test_a_passing_verdict_marks_nothing() -> None:
    assert field_errors([_verdict("BALANCE", VerdictSeverity.OK)]) == {}


def test_a_verdict_about_a_range_marks_both_limits() -> None:
    shown = field_errors(
        [_verdict("LEVEL_OUTSIDE_PRICE_BAND", VerdictSeverity.REFUSED)]
    )
    assert set(shown) == {"lower", "upper"}


def test_blocking_wins_over_advice_on_the_same_field_in_either_order() -> None:
    advice = _verdict("RANGE_OUTSIDE_ATR_BAND", VerdictSeverity.WARNING, "atr")
    block = _verdict("LEVEL_OUTSIDE_PRICE_BAND", VerdictSeverity.REFUSED, "band")
    for order in ((advice, block), (block, advice)):
        assert field_errors(order)["lower"].text == f"{BLOCKS}band"


def test_a_code_with_no_field_marks_nothing_and_has_no_field_to_focus() -> None:
    assert field_errors([_verdict("KEY_CANNOT_TRADE", VerdictSeverity.REFUSED)]) == {}
    assert field_of_code("KEY_CANNOT_TRADE") is None


def test_the_panel_marks_the_field_and_clears_it_when_the_verdict_goes(qtbot) -> None:
    panel = GridPanel()
    qtbot.addWidget(panel)
    verdict = _verdict("CAPITAL_ABOVE_BALANCE", VerdictSeverity.REFUSED, "too much")

    panel.show_verdicts((verdict,))
    assert panel.field_error_text("capital_quote") == "Blocks Start: too much"
    assert panel.capital.toolTip() == "Blocks Start: too much"

    panel.show_verdicts(())
    assert panel.field_error_text("capital_quote") == ""
    assert panel.capital.toolTip() == ""


def test_focusing_a_field_for_a_verdict_code(qtbot) -> None:
    panel = GridPanel()
    qtbot.addWidget(panel)
    panel.show()
    assert panel.focus_field("CAPITAL_ABOVE_BALANCE")
    qtbot.waitUntil(lambda: panel.capital.hasFocus())
    assert not panel.focus_field("KEY_CANNOT_TRADE")


def test_a_stop_loss_that_is_off_focuses_its_kind_not_its_disabled_value(qtbot) -> None:
    panel = GridPanel()
    qtbot.addWidget(panel)
    panel.set_config({"stop_loss": "off"})
    panel.show()
    assert panel.focus_field("STOP_LOSS_INSIDE_RANGE")
    qtbot.waitUntil(lambda: panel.stop_loss.kind.hasFocus())
