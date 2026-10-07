"""A label shows text as text: UI code makes labels with `plain_label` (`BUG-168`).

A bare `QLabel` is `Qt.AutoText`: a string that merely looks like HTML is drawn
as HTML. On 2026-10-07 an exchange's `502 Bad Gateway` page, carried in an
exception's message, was drawn in the Bots panel as a heading. Message text
that reaches a label comes from outside the app (an exchange, a file, a symbol
catalog), so the safe default is a property of how a label is made, not of each
call site remembering `setTextFormat`.

`src/support/ui_kit/plain_label.py` is the one place a `QLabel` is constructed;
it sets `Qt.PlainText`. What is found, anywhere in `src`:
- a `QLabel(...)` call outside that file;
- a class deriving `QLabel` whose file never calls `setTextFormat` (a subclass
  that is markup on purpose says so, where it is written).

Retire when: Qt makes `PlainText` the default of `QLabel` (Qt 7 has no such plan).
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_FACTORY = "src/support/ui_kit/plain_label.py"


def _is_qlabel(node: ast.expr) -> bool:
    """`QLabel` or `QtWidgets.QLabel`, however the module was imported."""
    return (isinstance(node, ast.Name) and node.id == "QLabel") or (
        isinstance(node, ast.Attribute) and node.attr == "QLabel"
    )


def untrusted_label_sites(source: str) -> list[str]:
    """Each place in `source` that makes a label which may render markup."""
    tree = ast.parse(source)
    says_its_format = any(
        isinstance(node, ast.Attribute) and node.attr == "setTextFormat"
        for node in ast.walk(tree)
    )
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_qlabel(node.func):
            found.append(f"line {node.lineno}: QLabel(...)")
        elif (
            isinstance(node, ast.ClassDef)
            and any(_is_qlabel(base) for base in node.bases)
            and not says_its_format
        ):
            found.append(f"line {node.lineno}: class {node.name}(QLabel)")
    return found


def _sources() -> list[tuple[str, Path]]:
    if not _SRC_ROOT.is_dir():
        raise FileNotFoundError(f"{_SRC_ROOT} does not exist; retarget this guard")
    return [
        (path.relative_to(_REPO_ROOT).as_posix(), path)
        for path in sorted(_SRC_ROOT.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def test_the_scan_has_a_subject() -> None:
    assert len(_sources()) > 500, "the scan found almost nothing in src"


def test_the_factory_exists_and_is_the_one_place_that_builds_a_label() -> None:
    assert (_REPO_ROOT / _FACTORY).is_file()
    assert untrusted_label_sites((_REPO_ROOT / _FACTORY).read_text("utf-8"))


def test_no_ui_code_builds_a_label_that_may_render_markup() -> None:
    found = {
        rel: hits
        for rel, path in _sources()
        if rel != _FACTORY and (hits := untrusted_label_sites(path.read_text("utf-8")))
    }
    assert not found, (
        "make the label with plain_label (src/support/ui_kit/plain_label.py); a "
        "subclass that is markup on purpose calls setTextFormat:\n"
        + "\n".join(f"{rel}: {', '.join(hits)}" for rel, hits in sorted(found.items()))
    )


def test_a_planted_bare_label_is_seen() -> None:
    assert untrusted_label_sites("label = QLabel(error_text)\n") == [
        "line 1: QLabel(...)"
    ]


def test_a_markup_subclass_is_seen_unless_it_says_so() -> None:
    bare = "class Cell(QLabel):\n    pass\n"
    explicit = (
        "class Cell(QLabel):\n    def __init__(self):\n"
        "        self.setTextFormat(Qt.TextFormat.RichText)\n"
    )
    assert untrusted_label_sites(bare) == ["line 1: class Cell(QLabel)"]
    assert untrusted_label_sites(explicit) == []


def test_a_label_reached_through_its_module_is_seen() -> None:
    assert len(untrusted_label_sites("x = QtWidgets.QLabel(text)\n")) == 1
    assert len(untrusted_label_sites("class C(QtWidgets.QLabel):\n    pass\n")) == 1


def test_the_factory_call_is_not_a_bare_label() -> None:
    assert untrusted_label_sites("label = plain_label(error_text)\n") == []
