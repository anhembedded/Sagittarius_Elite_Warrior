"""Controls are stock Qt widgets in the platform style; what styles or sizes them by hand only shrinks (`EPIC-033B`).

**Why this guard exists.** `ui-presentation-rule.md` asks for one look per
control kind: the platform's. Microsoft's Windows UX guidelines say "use the
system font, sizes, and colors" and "never make your own colors based on fixed
RGB values"; Qt's own documentation calls style sheets "a tool for prototyping
… not for the production look of an application". The 2026-10-04 UI review
counted 13 button styles, 133 `setStyleSheet` calls, 36 hand-set sizes and
52 colour literals. Each is a line of code, so each is counted here.

**The ratchet** is `baseline_stock_controls.json`: per rule, per file, the
calls found. A file over its count fails, and so does a new file; a file under
its count fails until the line is lowered, so freed room never stays. Every
count reaches zero when EPIC-033M closes, and this file becomes a ban.

**What each rule counts** (calls, by the attribute or name called):

* ``style_sheet`` — ``setStyleSheet``, ``apply_role``, ``StyledButton``.
* ``fixed_size`` — ``setFixedSize/Width/Height``, ``setMinimumSize/Width/Height``,
  ``setMaximumSize/Width/Height`` (the style decides control metrics).
* ``item_view_config`` — ``setSelectionBehavior``, ``setSelectionMode``,
  ``setEditTriggers``, ``setSortingEnabled``, ``setSectionResizeMode``,
  ``setAlternatingRowColors``: item views are configured by the engine's
  column specs (EPIC-033N), never per view.
* ``font_family`` — ``QFont("…")`` with a family literal, ``setFamily``,
  ``setFont`` on the application (fonts derive from the system font).
* ``color_literal`` — a ``"#rgb"``-style string or ``QColor`` built from one.
* ``checkable_button`` — ``setCheckable`` (state belongs in check boxes and
  radio buttons; Microsoft and KDE both say so).

Retire when: every count is zero (EPIC-033M); then the baseline file is
deleted and each rule is an outright ban.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_BASELINE_FILE = Path(__file__).with_name("baseline_stock_controls.json")

_CALLS: dict[str, frozenset[str]] = {
    "style_sheet": frozenset({"setStyleSheet", "apply_role", "StyledButton"}),
    "fixed_size": frozenset(
        {
            "setFixedSize",
            "setFixedWidth",
            "setFixedHeight",
            "setMinimumSize",
            "setMinimumWidth",
            "setMinimumHeight",
            "setMaximumSize",
            "setMaximumWidth",
            "setMaximumHeight",
        }
    ),
    "item_view_config": frozenset(
        {
            "setSelectionBehavior",
            "setSelectionMode",
            "setEditTriggers",
            "setSortingEnabled",
            "setSectionResizeMode",
            "setAlternatingRowColors",
        }
    ),
    "checkable_button": frozenset({"setCheckable"}),
}
RULES = (*_CALLS, "font_family", "color_literal")
_HEX_COLOR = re.compile(
    r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"
)

#: rule -> {path -> count}
Counts = dict[str, dict[str, int]]


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _first_arg_is_str(node: ast.Call) -> bool:
    return (
        bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    )


def findings(source: str) -> Counter[str]:
    """How many times each rule is broken in one module's source."""
    found: Counter[str] = Counter()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = _called_name(node)
            for rule, names in _CALLS.items():
                if name in names:
                    found[rule] += 1
            if name == "QFont" and _first_arg_is_str(node):
                found["font_family"] += 1
            if name == "setFamily":
                found["font_family"] += 1
            if (
                name == "setFont"
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"app", "QApplication", "qapp"}
            ):
                found["font_family"] += 1
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _HEX_COLOR.match(node.value)
        ):
            found["color_literal"] += 1
    return found


def measure(src_root: Path = _SRC_ROOT) -> Counts:
    if not src_root.is_dir():
        raise FileNotFoundError(f"{src_root} does not exist; retarget this guard")
    counts: Counts = {rule: {} for rule in RULES}
    for path in sorted(src_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(src_root.parent).as_posix()
        for rule, n in findings(path.read_text(encoding="utf-8")).items():
            counts[rule][rel] = n
    return counts


def ratchet_problems(baseline: Counts, current: Counts) -> list[str]:
    problems: list[str] = []
    for rule in sorted(set(baseline) | set(current)):
        was_map, now_map = baseline.get(rule, {}), current.get(rule, {})
        for path in sorted(set(was_map) | set(now_map)):
            was, now = was_map.get(path, 0), now_map.get(path, 0)
            if now > was:
                problems.append(
                    f"{rule} {path}: {now}, baseline {was} — use the stock control "
                    "and the platform style instead (ui-presentation-rule.md)"
                )
            elif now < was:
                problems.append(
                    f"{rule} {path}: {now}, baseline {was} — lower the baseline to match"
                )
    return problems


def _read_baseline() -> Counts:
    data: Counts = json.loads(_BASELINE_FILE.read_text(encoding="utf-8"))["counts"]
    return data


def test_the_scan_has_a_subject() -> None:
    current = measure()
    assert any(current[rule] for rule in RULES), "the scan found nothing in src"


def test_the_baseline_names_every_rule() -> None:
    assert set(_read_baseline()) == set(RULES)


def test_stock_controls_only_shrinks() -> None:
    problems = ratchet_problems(_read_baseline(), measure())
    assert not problems, "\n".join(problems)


def test_each_rule_is_seen() -> None:
    source = (
        "w.setStyleSheet('x')\nb.setFixedHeight(40)\nv.setSortingEnabled(True)\n"
        "f = QFont('Consolas')\nc = QColor('#1a2b3c')\nb.setCheckable(True)\n"
        "app.setFont(f)\n"
    )
    found = findings(source)
    assert found == Counter(
        {
            "style_sheet": 1,
            "fixed_size": 1,
            "item_view_config": 1,
            "font_family": 2,
            "color_literal": 1,
            "checkable_button": 1,
        }
    )


def test_stock_code_is_not_counted() -> None:
    source = "b = QPushButton('&Run')\nt = QTableView()\nf = QFont(app.font())\n"
    assert findings(source) == Counter()


def test_a_new_file_with_a_style_sheet_fails() -> None:
    problems = ratchet_problems({"style_sheet": {}}, {"style_sheet": {"src/x.py": 1}})
    assert len(problems) == 1 and problems[0].startswith("style_sheet src/x.py: 1")


def test_a_removed_call_must_lower_the_baseline() -> None:
    problems = ratchet_problems(
        {"fixed_size": {"src/x.py": 2}}, {"fixed_size": {"src/x.py": 1}}
    )
    assert problems == [
        "fixed_size src/x.py: 1, baseline 2 — lower the baseline to match"
    ]
