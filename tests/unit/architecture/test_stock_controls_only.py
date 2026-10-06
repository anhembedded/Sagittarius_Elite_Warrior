"""Controls are stock Qt widgets in the platform style; what styles or sizes them by hand is banned (`EPIC-033B`, `EPIC-033M`, `BOT-161`).

**Why this guard exists.** `ui-presentation-rule.md` asks for one look per
control kind: the platform's. Microsoft's Windows UX guidelines say "use the
system font, sizes, and colors" and "never make your own colors based on fixed
RGB values"; Qt's own documentation calls style sheets "a tool for prototyping
… not for the production look of an application". The 2026-10-04 UI review
counted 13 button styles, 133 `setStyleSheet` calls, 36 hand-set sizes and
52 colour literals. Each is a line of code, so each is counted here.

**The rule** is a ban: every count is zero. It was a ratchet
(`baseline_stock_controls.json`: per rule, per file, the calls found) until
`EPIC-033M` took the counts to zero rule by rule and `BOT-161` took the last
one, the colour literals of data series, to zero too; the baseline file is gone.

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

**One exemption:** ``color_literal`` is not counted in ``_SERIES_TABLE``,
``src/support/charting/contracts/series_colours.py``, the one table of data series
colours (indicator lines, strategy lines, the chart's bull and bear). A
strategy in a module's ``domain/`` names a series
(``support/charting/contracts/chart_series.py``) and never a colour; the UI
asks the table. Any other file holding a hex colour fails, and the exemption
is a single path, so a second table cannot grow beside it
(``test_the_one_exemption_is_the_series_table``).

``BUG-008``'s unscoped-container check went with the last style sheet, as it
said it would: a ban on ``setStyleSheet`` covers it.

Retire when: the engine owns the series table and no application file names a
data colour at all.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
#: The one file allowed to write a data series colour (`BOT-161`); it is the
#: guard's only named exemption.
_SERIES_TABLE = "src/support/charting/contracts/series_colours.py"

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
    """The calls found per rule, per file. The series table's colours are the
    one thing not counted (`_SERIES_TABLE`)."""
    if not src_root.is_dir():
        raise FileNotFoundError(f"{src_root} does not exist; retarget this guard")
    counts: Counts = {rule: {} for rule in RULES}
    for path in sorted(src_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(src_root.parent).as_posix()
        found = findings(path.read_text(encoding="utf-8"))
        if rel == _SERIES_TABLE:
            del found["color_literal"]
        for rule, n in found.items():
            counts[rule][rel] = n
    return counts


def test_the_scan_has_a_subject() -> None:
    sources = [
        path for path in _SRC_ROOT.rglob("*.py") if "__pycache__" not in path.parts
    ]
    assert sources, "the scan found no module in src"


def test_no_control_is_styled_sized_or_coloured_by_hand() -> None:
    """The ban: every rule is at zero, outside the one series table."""
    found = {
        f"{rule} {path}": n
        for rule, files in measure().items()
        for path, n in files.items()
    }
    assert not found, (
        "use the stock control and the platform style, and name a data series "
        "colour in the series table (ui-presentation-rule.md): "
        + ", ".join(f"{where}: {n}" for where, n in sorted(found.items()))
    )


def test_the_one_exemption_is_the_series_table() -> None:
    """The exemption names a file that exists and really holds colours, so it
    cannot linger as a free pass after the table moves, and it names one path."""
    table = _REPO_ROOT / _SERIES_TABLE
    assert table.is_file(), f"{_SERIES_TABLE} moved; retarget the exemption"
    assert findings(table.read_text(encoding="utf-8"))["color_literal"] > 0


def test_a_colour_outside_the_series_table_is_counted(tmp_path: Path) -> None:
    root = tmp_path / "src"
    (root / "support" / "charting" / "contracts").mkdir(parents=True)
    (root / "support" / "charting" / "contracts" / "series_colours.py").write_text(
        "A = '#112233'\n"
    )
    (root / "support" / "charting" / "other.py").write_text("C = '#778899'\n")
    (root / "elsewhere.py").write_text("B = '#445566'\n")

    counts = measure(root)

    # The table is excused by its path; a file beside it, or anywhere else, is not.
    assert counts["color_literal"] == {
        "src/elsewhere.py": 1,
        "src/support/charting/other.py": 1,
    }
