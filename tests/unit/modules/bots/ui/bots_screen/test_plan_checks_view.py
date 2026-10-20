"""`BOT-209` — the checks list as a widget: what it shows, in what order, folded how."""

from __future__ import annotations

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks import (
    PlanChecks,
    plan_checks_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_checks_view import (
    HEADING,
    PlanChecksView,
)

OK, WARNING, REFUSED = (
    VerdictSeverity.OK,
    VerdictSeverity.WARNING,
    VerdictSeverity.REFUSED,
)
_LONG = (
    "The thinnest grid step is 0.31234% (6.85 USDT, from 2200 to 2206.85). "
    "At least 0.50% is advised. This is advice; the bot can still be created."
)


def _v(
    severity: VerdictSeverity, title: str, summary: str = "", reason: str = ""
) -> Verdict:
    return Verdict(
        severity,
        title.upper().replace(" ", "_"),
        reason or f"{title} holds",
        title=title,
        summary=summary,
    )


def _view(qtbot, *verdicts: Verdict) -> PlanChecksView:
    checks = PlanChecksView()
    qtbot.addWidget(checks.body)
    checks.body.resize(520, 300)
    checks.body.show()
    checks.show_checks(plan_checks_of(verdicts))
    return checks


def test_errors_and_warnings_are_listed_first_and_the_rest_fold_into_one_count(
    qtbot,
) -> None:
    checks = _view(
        qtbot,
        _v(OK, "Fees"),
        _v(WARNING, "Step", "Step 0.31% is thin"),
        _v(OK, "Band"),
        _v(REFUSED, "Capital", "Capital is above the balance"),
    )

    assert checks.rows() == (
        (HEADING, "1 blocking Start, 1 warning"),
        ("Capital", "Capital is above the balance"),
        ("Step", "Step 0.31% is thin"),
        ("2 checks passed", ""),
    )


def test_opening_the_count_lists_the_passed_checks_and_it_stays_open_when_rejudged(
    qtbot,
) -> None:
    checks = _view(qtbot, _v(OK, "Fees"), _v(OK, "Band"), _v(WARNING, "Step", "thin"))

    checks.open_passed(True)

    assert [title for title, _ in checks.rows()][-3:] == [
        "2 checks passed",
        "Fees",
        "Band",
    ]
    checks.show_checks(plan_checks_of((_v(OK, "Fees"), _v(OK, "Band"), _v(OK, "Gap"))))
    assert checks.passed_row_is_open()
    assert [title for title, _ in checks.rows()][-4:] == [
        "3 checks passed",
        "Fees",
        "Band",
        "Gap",
    ]
    checks.open_passed(False)
    assert [title for title, _ in checks.rows()] == [HEADING, "3 checks passed"]


def test_the_whole_sentence_is_the_tooltip_and_the_row_says_one_line(qtbot) -> None:
    checks = _view(qtbot, _v(WARNING, "Step", "Step 0.31% is thin", _LONG))

    assert checks.rows()[1] == ("Step", "Step 0.31% is thin")
    assert "0.31234%" in checks.tooltip_of("Step")
    assert "0.31234%" not in "".join(finding for _, finding in checks.rows())


def test_every_attention_row_carries_an_icon_and_a_passed_one_is_quiet(qtbot) -> None:
    checks = _view(qtbot, _v(REFUSED, "Capital"), _v(WARNING, "Step"), _v(OK, "Fees"))
    checks.open_passed(True)

    root = checks.model.invisibleRootItem().child(0, 0)
    attention = [root.child(row, 0) for row in range(2)]
    folded = root.child(2, 0)

    assert all(not item.icon().isNull() for item in attention)
    assert not folded.icon().isNull()
    assert folded.child(0, 0).icon().isNull()
    assert checks.view.model().rowCount() == 1


def test_nothing_to_judge_hides_the_list(qtbot) -> None:
    checks = _view(qtbot, _v(WARNING, "Step"))
    assert checks.body.isVisible()

    checks.show_checks(PlanChecks())

    assert not checks.body.isVisible()
    assert checks.rows() == ()


def test_the_list_is_as_tall_as_its_rows_and_scrolls_by_no_bar_of_its_own(
    qtbot,
) -> None:
    checks = _view(qtbot, *(_v(WARNING, f"Check {n}", "x " * 40) for n in range(5)))

    view = checks.view
    assert view.verticalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert view.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    qtbot.waitUntil(lambda: view.height() >= view.sizeHint().height() - 2)
