"""The booted app conforms to the desktop rule, per mode; known failures only shrink (`EPIC-033B`).

**Why this suite exists.** HLD §11.5 listed workbench rules as "enforced" while
only the `.qml` ban had a test, and the 2026-10-04 UI review had to measure
the rest by hand: no menu bar, one mode with docks, styled and oversized
controls, scroll areas inside scroll areas, labels whose `&` turned into a
mnemonic. These are properties of the composed window, which no file scan
sees, so this suite boots the real app (`main_window`) and checks every
navigable mode, at each of `WINDOW_SIZES` (`EPIC-033C`). The checks live in
`workbench_widget_checks.py` and `workbench_layout_checks.py`; each cites
`ui-presentation-rule.md`, which cites its source (Microsoft's Windows UX
guidelines, KDE HIG, Qt).

**The ratchet** is `baseline_workbench_conformance.json`: mode -> the checks it
fails today at every size, `mode@WxH` -> those it fails at that size only. A
check failing that is not listed fails the suite; a listed check that now
passes fails too, until its line is removed. The baseline is empty when
EPIC-033M closes.

Retire when: the baseline is empty and every check is a plain assertion.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QMainWindow,
)
from Sagittarius_Elite_Warrior.src.shell.developer_mode.developer_screen import (
    DEVELOPER_ROUTE,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_layout_checks import (
    fit_problems,
    object_name_problems,
    reset_layout_problems,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_text_checks import (
    column_problems,
    combo_problems,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_widget_checks import (
    Check,
    access_key_problems,
    control_height_problems,
    duplicate_button_problems,
    font_problems,
    item_view_problems,
    menu_bar_problems,
    mnemonic_problems,
    nested_scroll_problems,
    perspective_problems,
    separator_problems,
    style_sheet_problems,
    toolbar_in_menu_problems,
    toolbar_problems,
    toolbar_text_problems,
    view_menu_problems,
    workbench_problems,
)

BASELINE_FILE = Path(__file__).with_name("baseline_workbench_conformance.json")
_SHELL = "shell"
#: The rule's minimum usable size (§3), a common laptop and a full-HD screen.
WINDOW_SIZES = ((1024, 700), (1366, 768), (1920, 1080))


MODE_CHECKS: dict[str, Check] = {
    "workbench_host": workbench_problems,
    "docks_in_view_menu": view_menu_problems,
    "no_style_sheet": style_sheet_problems,
    "control_height": control_height_problems,
    "no_nested_scroll": nested_scroll_problems,
    "toolbar_actions_only": toolbar_problems,
    "toolbar_actions_in_a_menu": toolbar_in_menu_problems,
    "toolbar_text_matches_menu": toolbar_text_problems,
    "no_button_duplicates_a_command": duplicate_button_problems,
    "item_view_conventions": item_view_problems,
    "columns_shown_whole": column_problems,
    "combo_text_shown_whole": combo_problems,
    "mnemonics_escaped": mnemonic_problems,
    "access_keys_unique": access_key_problems,
    "menu_separators_between_groups": separator_problems,
    "perspective_round_trip": perspective_problems,
    "bars_named_uniquely": object_name_problems,
    # Last: it rearranges the mode, then puts the default back.
    "reset_layout_restores_default": reset_layout_problems,
}
SHELL_CHECKS: dict[str, Callable[[QMainWindow], list[str]]] = {
    "menu_bar_order": menu_bar_problems,
    "system_font": font_problems,
}


def _size_label(size: QSize) -> str:
    return f"{size.width()}x{size.height()}"


def _read_baseline() -> dict[str, list[str]]:
    data: dict[str, list[str]] = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))[
        "failing"
    ]
    return data


def measure(
    window: QMainWindow, navigate: Callable[[str], dict], qapp, size: QSize
) -> dict[str, dict[str, list[str]]]:
    """mode -> check -> problems, for the shell and every navigable mode."""
    report: dict[str, dict[str, list[str]]] = {
        _SHELL: {name: check(window) for name, check in SHELL_CHECKS.items()}
    }
    for route in window.navigation.modes():
        navigate(route)
        for _ in range(3):
            qapp.processEvents()
        # The mode's host, which the shell switches: the screen's view is
        # its central widget (`EPIC-033C`).
        page = window.hosts[route]
        report[route] = {
            name: check(window, page) for name, check in MODE_CHECKS.items()
        }
        report[route]["fits_the_window"] = fit_problems(window, page, size)
    return report


def ratchet_problems(
    baseline: dict[str, list[str]],
    report: dict[str, dict[str, list[str]]],
    size: QSize,
) -> list[str]:
    """`mode` lists what a mode fails at every size, `mode@WxH` what it fails
    at that size only."""
    label = _size_label(size)
    problems = []
    for mode, checks in sorted(report.items()):
        everywhere = set(baseline.get(mode, []))
        listed = everywhere | set(baseline.get(f"{mode}@{label}", []))
        for check, found in sorted(checks.items()):
            if found and check not in listed:
                problems.append(f"{mode}@{label}/{check}: " + "; ".join(found[:5]))
            elif not found and check in everywhere:
                problems.append(
                    f"{mode}/{check}: passes at {label} — list it under the "
                    "sizes it still fails at, or remove it from the baseline"
                )
            elif not found and check in listed:
                problems.append(
                    f"{mode}@{label}/{check}: passes now — remove it from the baseline"
                )
    sizes = {_size_label(QSize(*s)) for s in WINDOW_SIZES}
    for key in sorted(baseline):
        mode, _, at = key.partition("@")
        if at and at not in sizes:
            problems.append(f"{key}: no such window size — remove it from the baseline")
        elif mode not in report and at in ("", label):
            problems.append(
                f"{key}: no such mode any more — remove it from the baseline"
            )
    return problems


@pytest.mark.parametrize(
    "size", [QSize(*s) for s in WINDOW_SIZES], ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
@pytest.mark.parametrize("app_engine", [True], indirect=True)
def test_workbench_conformance(qapp, main_window, navigate, size: QSize) -> None:
    """Each check at each size. While a mode does not fit (`fits_the_window`)
    the window stays at its own minimum, bigger than `size`, and the other
    checks measure there."""
    main_window.resize(size)
    main_window.show()
    report = measure(main_window, navigate, qapp, size)
    # Booted with developer mode on, so the Developer mode is measured too
    # (`EPIC-033P`), and with no baseline row of its own.
    assert DEVELOPER_ROUTE in report
    problems = ratchet_problems(_read_baseline(), report, size)
    assert not problems, "\n".join(problems)


def test_a_new_failure_fails_and_a_fixed_one_must_leave_the_baseline() -> None:
    report = {
        "trade": {
            "no_style_sheet": ["QLabel 'x' has a style sheet"],
            "control_height": [],
        }
    }
    problems = ratchet_problems({"trade": ["control_height"]}, report, QSize(1366, 768))
    assert problems == [
        (
            "trade/control_height: passes at 1366x768 — list it under the sizes "
            "it still fails at, or remove it from the baseline"
        ),
        "trade@1366x768/no_style_sheet: QLabel 'x' has a style sheet",
    ]


def test_a_size_key_counts_at_its_own_size_only() -> None:
    report = {"backtest": {"fits_the_window": ["needs 1400x600"]}}
    baseline = {"backtest@1024x700": ["fits_the_window"], "old@1920x1080": ["x"]}

    assert ratchet_problems(baseline, report, QSize(1024, 700)) == []
    assert ratchet_problems(baseline, report, QSize(1366, 768)) == [
        "backtest@1366x768/fits_the_window: needs 1400x600"
    ]
    assert ratchet_problems(baseline, {"backtest": {}}, QSize(1920, 1080)) == [
        "old@1920x1080: no such mode any more — remove it from the baseline"
    ]
    assert ratchet_problems({"x@800x600": []}, {}, QSize(1024, 700)) == [
        "x@800x600: no such window size — remove it from the baseline"
    ]
