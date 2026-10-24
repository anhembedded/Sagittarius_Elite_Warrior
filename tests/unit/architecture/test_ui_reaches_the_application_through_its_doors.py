"""The UI reaches the application only through its doors, and the debt around them only shrinks
(`EPIC-048A`, ADR D1-D4 of `EPIC-048`).

**The rule** is `architecture-rule.md` §3.1: a file under `src/modules/*/ui/` reaches the
application through the command dispatcher and the bus, plus the allowlist named on the rule's own
line, which `ui_doors_scan.py` reads from there. De-risk R7 measured 215 imports around the doors
and 30 container-taking functions at `5ddbd68` (`EPIC-047` `DERISK.md` §7.3); nothing stopped a
216th, and a remote backend cannot stand behind a screen that bypasses the doors.

**The ratchet.** `baseline_ui_doors.json` holds each screen area's counts per class, in three
sections: `around_the_doors` (an application function or non-data class, a behavioural port, an
adapter), `application_data` (a dataclass, an enum, a constant or an exception from the application
layer; ADR D4 clears these last) and `takes_the_container`. A count may never rise, and a count that
falls fails until the baseline is lowered to it in the same pull request, so no entry leaves room
to grow back into (`P8`; the shape of `test_god_files_only_shrink.py`). Counts, not file lists, so
an unrelated rename does not churn the file. Each failure names the baseline and the measured
value of every count that moved.

Retire when: every section of the baseline is empty (`EPIC-048D` done); the guard then becomes a
plain ban with no baseline file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import sagittarius_engine.interfaces

from .ui_doors_scan import (
    MODULES_ROOT,
    RULE_FILE,
    Hit,
    allowlist,
    baseline_shape,
    classify,
    scan,
    section_of,
    ui_files,
)

_BASELINE_FILE = Path(__file__).with_name("baseline_ui_doors.json")
#: The doors themselves: the rule's allowlist line must name them (ADR D1).
_DOORS = frozenset({"ICommandDispatcher", "IEventPublisher", "IEventBus"})


@pytest.fixture(scope="module")
def hits() -> list[Hit]:
    return scan()


def _baseline() -> dict[str, dict[str, dict[str, int]]]:
    loaded: dict[str, dict[str, dict[str, int]]] = json.loads(
        _BASELINE_FILE.read_text(encoding="utf-8")
    )
    return loaded


def _changed(
    measured: dict[str, dict[str, dict[str, int]]], rising: bool
) -> dict[tuple[str, str, str], tuple[int, int]]:
    """`(section, area, kind) -> (baseline, measured)` for every count that rose, or that fell."""
    recorded = _baseline()
    changed: dict[tuple[str, str, str], tuple[int, int]] = {}
    for section in set(measured) | set(recorded):
        areas = set(measured.get(section, {})) | set(recorded.get(section, {}))
        for area in areas:
            now = measured.get(section, {}).get(area, {})
            then = recorded.get(section, {}).get(area, {})
            for kind in set(now) | set(then):
                before, after = then.get(kind, 0), now.get(kind, 0)
                if (after > before) if rising else (after < before):
                    changed[(section, area, kind)] = (before, after)
    return changed


def test_the_rule_names_the_doors_on_its_allowlist_line() -> None:
    named = allowlist()
    assert named >= _DOORS, (
        f"the allowlist line of {RULE_FILE.name} §3.1 must name the doors {sorted(_DOORS)}; "
        f"it names {sorted(named)}"
    )


def test_every_allowlisted_name_is_a_real_contract() -> None:
    """A name no class carries allows nothing today and would let a future class of that name in
    unreviewed; fail on it. A contract lives under a `contracts` package of `src/` or in the
    engine's `interfaces` package (`IEventBus`, `IThreadManager`)."""
    engine_interfaces = Path(sagittarius_engine.interfaces.__file__).parent
    files = [
        *MODULES_ROOT.parent.glob("**/contracts/**/*.py"),
        *engine_interfaces.glob("*.py"),
    ]
    defined = {
        match
        for path in files
        for match in re.findall(
            r"^class (I[A-Za-z0-9]+)\b", path.read_text(encoding="utf-8"), re.MULTILINE
        )
    }
    unknown = allowlist() - defined
    assert not unknown, f"the allowlist names no contract class: {sorted(unknown)}"


@pytest.mark.parametrize(
    ("module", "name", "expected"),
    [
        ("src.modules.bots", "application", "APP_OTHER"),
        ("src.modules.bots.application", "BotPlan", "APP_OTHER"),
        ("src.modules.bots.application", "services", "APP_SERVICE"),
        ("src.modules.bots", "adapters", "ADAPTER"),
        ("src.modules.bots.application.services.readiness", "assess", "APP_SERVICE"),
        ("src.modules.bots.application.queries.get_bot", "GetBotQuery", None),
        ("src.modules.bots.domain", "application_word", None),
    ],
    ids=[
        "bare-app",
        "app-package",
        "app-services",
        "bare-adapters",
        "service",
        "query",
        "word",
    ],
)
def test_a_layer_is_matched_on_whole_segments(
    module: str, name: str, expected: str | None
) -> None:
    """A bare package import reaches the layer as surely as a module inside it (review of #730)."""
    assert classify(module, name, frozenset()) == expected


def test_the_scan_reads_the_ui_tree() -> None:
    assert ui_files(), (
        "no .py file under src/modules/*/ui/: the tree moved, retarget the scan"
    )


def test_no_count_around_the_doors_rises(hits: list[Hit]) -> None:
    risen = _changed(baseline_shape(hits), rising=True)
    detail = "\n".join(
        f"  {section} / {area} / {kind}: {before} -> {after}\n"
        + "\n".join(
            f"    {hit}"
            for hit in hits
            if hit.area == area and hit.kind == kind and section_of(hit.kind) == section
        )
        for (section, area, kind), (before, after) in sorted(risen.items())
    )
    assert not risen, (
        "a UI file reaches the application around its doors (architecture-rule.md §3.1). "
        "Send a query or a command through ICommandDispatcher, or listen on the bus, instead of "
        f"importing it. Counts that rose (baseline -> measured), with every hit of that class:\n{detail}"
    )


def test_a_count_that_fell_is_lowered_in_the_baseline(hits: list[Hit]) -> None:
    fallen = _changed(baseline_shape(hits), rising=False)
    detail = "\n".join(
        f"  {section} / {area} / {kind}: {before} -> {after}"
        for (section, area, kind), (before, after) in sorted(fallen.items())
    )
    assert not fallen, (
        f"these counts fell; lower {_BASELINE_FILE.name} to the measured value in this same pull "
        f"request, so the ratchet does not leave room to grow back (baseline -> measured):\n{detail}"
    )


def test_the_baseline_has_its_three_sections() -> None:
    assert set(_baseline()) == set(baseline_shape([])), (
        f"{_BASELINE_FILE.name} must hold exactly the sections {sorted(baseline_shape([]))}"
    )
