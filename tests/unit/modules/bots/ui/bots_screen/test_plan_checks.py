"""`BOT-209` — a plan's checks: the ones that need attention first, the passed ones counted.

Pure over `Verdict`s: each rule is read off `plan_checks_of` without a widget.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_plan_judge import (
    verdict_line,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks import (
    PlanChecks,
    plan_checks_of,
)

OK, WARNING, REFUSED = (
    VerdictSeverity.OK,
    VerdictSeverity.WARNING,
    VerdictSeverity.REFUSED,
)


def _v(severity: VerdictSeverity, code: str, **fields: object) -> Verdict:
    return Verdict(severity, code, f"{code} in full", **fields)  # type: ignore[arg-type]


def test_refusals_come_first_then_warnings_and_each_keeps_the_kinds_order() -> None:
    checks = plan_checks_of(
        (
            _v(OK, "A"),
            _v(WARNING, "B"),
            _v(REFUSED, "C"),
            _v(WARNING, "D"),
            _v(REFUSED, "E"),
            _v(OK, "F"),
        )
    )

    assert [c.code for c in checks.attention] == ["C", "E", "B", "D"]
    assert [c.code for c in checks.passed] == ["A", "F"]


def test_the_passed_checks_are_one_count_not_a_list() -> None:
    fourteen = tuple(_v(OK, f"P{n}") for n in range(14))

    checks = plan_checks_of((*fourteen, _v(WARNING, "W")))

    assert checks.passed_text == "14 checks passed"
    assert plan_checks_of(fourteen[:1]).passed_text == "1 check passed"
    assert [c.code for c in checks.attention] == ["W"]


def test_the_tally_says_how_the_plan_stands_in_words() -> None:
    assert plan_checks_of(()).tally == ""
    assert plan_checks_of((_v(OK, "A"),)).tally == "all passed"
    assert (
        plan_checks_of((_v(REFUSED, "A"), _v(WARNING, "B"), _v(WARNING, "C"))).tally
        == "1 blocking Start, 2 warnings"
    )
    assert plan_checks_of((_v(WARNING, "B"),)).tally == "1 warning"


def test_a_check_is_its_title_its_one_line_and_its_whole_sentence() -> None:
    verdict = Verdict(
        WARNING,
        "STEP_BELOW_MINIMUM",
        "The thinnest grid step is 0.31234%, from 2200.00 to 2208.31. Slippage can eat it.",
        {"thinnest_step": Decimal("0.0031234")},
        title="Grid step room for slippage",
        summary="Step 0.31% is thin; 0.50%+ advised",
    )

    (check,) = plan_checks_of((verdict,)).attention

    assert check.title == "Grid step room for slippage"
    assert check.headline == "Step 0.31% is thin; 0.50%+ advised"
    # The whole sentence keeps its exact numbers, as the verdict list always wrote it.
    assert check.detail == verdict_line(verdict)
    assert "0.31234%" in check.detail


def test_a_verdict_with_no_summary_is_its_own_reason_and_a_side_names_its_title() -> (
    None
):
    verdict = Verdict(
        OK,
        "LIQUIDATION_ESTIMATE",
        "Estimated liquidation of the long",
        subject="long",
        title="Liquidation distance",
    )

    (check,) = plan_checks_of((verdict,)).passed

    assert check.headline == "Estimated liquidation of the long"
    assert check.title == "Liquidation distance (long)"


def test_a_kind_that_names_no_title_still_gets_a_readable_one() -> None:
    (check,) = plan_checks_of((_v(WARNING, "RANGE_TOO_WIDE"),)).attention

    assert check.title == "Range too wide"


def test_nothing_judged_is_an_empty_list() -> None:
    assert plan_checks_of(()) == PlanChecks()
    assert PlanChecks().everything == ()
