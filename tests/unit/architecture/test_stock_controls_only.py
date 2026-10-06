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
* ``color_literal`` — a string constant, other than a docstring, holding a
  ``#rgb``/``#rrggbb``/``#rrggbbaa`` value anywhere in it: a bare colour, rich
  text (``<span style="color:#F3BA2F">``) or a QSS constant alike.
  ``QColor(r, g, b)`` with integers and ``QFont(family=…)`` by keyword are not
  seen; review row H1 holds them.
* ``checkable_button`` — ``setCheckable`` (state belongs in check boxes and
  radio buttons; Microsoft and KDE both say so). A checkable ``QAction`` is
  the rule's own third option (§6: "a checkable action"), so a call on a name
  the same function assigned from ``QAction(...)``, or from one of the
  module's functions annotated ``-> QAction``, is not counted.

**Bans since EPIC-033M:** every rule but ``color_literal``. The kit, ``Palette``
and the theme bootstrap are deleted and their counts are zero, so their
baseline entries must stay empty (``test_every_rule_but_colour_literals_is_a_ban``).
``BUG-008``'s unscoped-container check went with the last style sheet, as it
said it would: a ban on ``setStyleSheet`` covers it.

**Still a ratchet:** ``color_literal``, for data series colours (indicator
lines, strategy markers, the chart's bull and bear), which are not chrome.

Retire when: ``color_literal`` is zero too; then the baseline file is deleted
and this file is a ban outright.
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
#: The one rule still ratcheted; every other rule is a ban (`EPIC-033M`).
_RATCHETED = frozenset({"color_literal"})

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
_HEX_COLOR = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")

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


def _docstrings(tree: ast.Module) -> set[int]:
    owners = [
        tree,
        *(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        ),
    ]
    return {
        id(owner.body[0].value)
        for owner in owners
        if owner.body
        and isinstance(owner.body[0], ast.Expr)
        and isinstance(owner.body[0].value, ast.Constant)
    }


def _target_name(node: ast.expr) -> str | None:
    """`action` for `action`, `box_zoom` for `self.box_zoom`."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


_Scope = ast.Module | ast.FunctionDef | ast.AsyncFunctionDef


def _own_nodes(scope: _Scope) -> list[ast.AST]:
    """The nodes of one scope, not those of the functions nested in it."""
    nodes: list[ast.AST] = []
    pending: list[ast.AST] = list(ast.iter_child_nodes(scope))
    while pending:
        node = pending.pop()
        nodes.append(node)
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            pending.extend(ast.iter_child_nodes(node))
    return nodes


def _checkable_actions(tree: ast.Module) -> set[int]:
    """The `setCheckable` calls made on a `QAction`: on a name the same
    function (or module body) assigned from `QAction(...)` or from one of the
    module's functions annotated `-> QAction`. Scoped to the function, so a
    `self.toggle` action in one method does not excuse a `toggle` button in
    another."""
    makers = {"QAction"} | {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and isinstance(node.returns, ast.Name)
        and node.returns.id == "QAction"
    }
    scopes: list[_Scope] = [tree]
    scopes += [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    exempt: set[int] = set()
    for scope in scopes:
        nodes = _own_nodes(scope)
        names = {
            name
            for node in nodes
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and _called_name(node.value) in makers
            for target in node.targets
            if (name := _target_name(target))
        }
        exempt.update(
            id(node)
            for node in nodes
            if isinstance(node, ast.Call)
            and _called_name(node) == "setCheckable"
            and isinstance(node.func, ast.Attribute)
            and _target_name(node.func.value) in names
        )
    return exempt


def findings(source: str) -> Counter[str]:
    """How many times each rule is broken in one module's source."""
    found: Counter[str] = Counter()
    tree = ast.parse(source)
    docstrings = _docstrings(tree)
    checkable_actions = _checkable_actions(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _called_name(node)
            if id(node) in checkable_actions:
                continue
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
            and id(node) not in docstrings
            and _HEX_COLOR.search(node.value)
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


def test_every_rule_but_colour_literals_is_a_ban() -> None:
    """`EPIC-033M`: the kit is gone and these rules are at zero, so each is a
    ban. An entry added to the baseline for one of them fails here, before it
    could excuse a new style sheet, size or font."""
    baseline = _read_baseline()
    allowed = {rule: files for rule, files in baseline.items() if files}
    assert set(allowed) <= _RATCHETED, allowed


def test_a_colour_inside_rich_text_or_qss_is_seen_and_a_docstring_is_not() -> None:
    source = (
        '"""Fixes PR #268 and #abc."""\n'
        'lbl.setText("<span style=\\"color:#F3BA2F\\">up</span>")\n'
        'SHEET = "QFrame { border: 1px solid #1a2b3c; }"\n'
    )
    assert findings(source) == Counter({"color_literal": 2})


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


def test_a_checkable_action_is_not_a_checkable_button() -> None:
    source = (
        "action = QAction('&Box zoom', self)\naction.setCheckable(True)\n"
        "self.box = QAction('&Box', self)\nself.box.setCheckable(True)\n"
        "def _make(text) -> QAction:\n    return QAction(text)\n"
        "self.made = self._make('&Made')\nself.made.setCheckable(True)\n"
        "button = QPushButton('&Box')\nbutton.setCheckable(True)\n"
    )
    assert findings(source) == Counter({"checkable_button": 1})


def test_an_action_in_one_method_does_not_excuse_a_button_in_another() -> None:
    """Review of PR #351: the exemption once matched names module-wide."""
    source = (
        "class A:\n"
        "    def build(self):\n"
        "        self.toggle = QAction('&Toggle', self)\n"
        "        self.toggle.setCheckable(True)\n"
        "    def other(self, panel):\n"
        "        panel.toggle = QPushButton('&Toggle')\n"
        "        panel.toggle.setCheckable(True)\n"
    )
    assert findings(source) == Counter({"checkable_button": 1})


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
