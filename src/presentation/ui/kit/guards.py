"""
@brief Static guards for the app's widget kit — the QtWidgets counterparts
to the QML kit's `tokens.qml_literal_guard`/`kit.raw_primitive_guard`
(EPIC-006, see `Sagittarius_Elite_Warrior/Tasks/epics/EPIC-006_drop_qml/
DECISION_2026-08-24_widget_architecture.md` §6).

@details
Three guards. Two match a QML one each has a direct counterpart for:

- `find_inline_stylesheets` — no hardcoded colour literal outside
  `kit/style.py` (the one file `apply_role()`/`_build_qss()` live in).
  Counterpart to `tokens.qml_literal_guard.find_literal_colors`.
- `find_unscoped_container_stylesheets` — no `setStyleSheet()` written as a
  bare property list on a widget that owns a layout. A list with no selector
  is Qt's **universal selector**: it repaints every descendant that has no
  rule of its own, handing the container's border and background to each
  child inside it. Harmless on a leaf, which is why the check only reports
  widgets that actually have children. This is `BUG-008`, and it has since
  recurred four more times in the consuming app — a guard, not a fix, is
  what stops the fifth.
- `find_bare_qt_base_widgets` — no `class X(QFrame)`/`class X(QDialog)`/
  `class X(QWidget)` outside `kit/surface.py`/`kit/overlay.py`
  themselves, barring a `# base-exempt: <reason>` line. Counterpart to
  `kit.raw_primitive_guard.find_raw_primitives` ("no raw primitive authored
  outside the kit").

The coverage-guard counterpart (`kit.gallery_coverage_guard`'s QtWidgets
equivalent) exists as of EPIC-007C, but not as a function here: it needs a
running `QApplication` to construct the gallery, which every other guard in
this module deliberately does not. It lives in
`tests/unit/presentation/ui/kit/test_showcase_coverage.py`, reading
`tools.kit_showcase.showcased_types()`, and fails when a type in
`kit.__all__` is never built by the showcase.

All three scan source without importing it, so none needs Qt. Within *this* repo they are
still exercised only through `tmp_path` fixtures — pointing them at
`sagittarius_engine/` itself remains outstanding.

The consuming app wired them up in EPIC-007D/E
(`tests/unit/presentation/ui/test_widget_guards_hold.py`): colour literals
locked at zero, bare Qt bases held under a ratchet that may only fall. That
is what `colour_source_names` exists for — an app's palette module is its
`style.py`, and until it could be named, the guard reported that file for
containing the very tokens it defines, which put zero out of reach.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

#: Same three lengths QML's colour guard matches (`#rgb`/`#rrggbb`/
#: `#aarrggbb`) — Qt's QSS colour literal syntax accepts the same forms.
_HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")

#: Same exemption convention as `qml_literal_guard._EXEMPT_MARKER` — a
#: deliberate, reviewed exception, visible on the same line as the literal.
_EXEMPT_MARKER = "token-exempt"

#: The one file inline-stylesheet literals are permitted in, for this
#: package's own tree. A consuming app keeps its colours somewhere else —
#: the reference consumer's is `assets/palette.py` — and names it through
#: `find_inline_stylesheets`'s `colour_source_names`. Hardcoding this one
#: name meant an app could never reach zero findings: the file defining its
#: tokens was itself reported, fifteen times, for containing tokens.
_STYLE_MODULE_NAME = "style.py"

#: `class Name(QFrame)` / `class Name(QDialog)` / `class Name(QWidget)` as a
#: direct base — matches only when the class body opens right after (a
#: trailing `metaclass=...` kwarg or multi-base declaration is out of scope
#: for this codebase's current style, same "match the real shape, not every
#: hypothetical" call `raw_primitive_guard` makes for its own two controls).
#:
#: `QWidget` joined the set in EPIC-007A. Measured on the consuming app the
#: day it was added: `QFrame`/`QDialog` alone found 12 classes in
#: `Sagittarius_Elite_Warrior/src/presentation/ui`, while 9 more were
#: surfaces authored as `class X(QWidget)` and sailed straight through —
#: `LogPanelWidget`, `AppProgressBarWidget`, `TimeRangeCardWidget`,
#: `DevBoardPanel`, `BackTestTopPanel`, `BackTestTradeLogsPanel`,
#: `DynamicTabBarWidget`, `_CachedFrameOverlay`, `_BotParamFieldWidget`. The
#: "12" this guard used to report was a floor, not a count.
_BARE_QT_BASE_RE = re.compile(r"^\s*class\s+\w+\((QFrame|QDialog|QWidget)\)\s*:")

#: Files where `Surface`/`Overlay` themselves legitimately extend
#: `QFrame`/`QDialog` directly — the one sanctioned place per base.
#:
#: `QWidget` has no entry here on purpose: this package derives no surface
#: from it (`Surface` is a `QFrame`, `Overlay` a `QDialog`), so there is no
#: sanctioned file to name. A legitimate `QWidget` base outside this package
#: — a pure layout composite, an MVC view root — is waved through by
#: `_BASE_EXEMPT_RE` below, per case and with its reason in the source,
#: rather than by exempting a whole file.
_BASE_DEFINITION_FILES = frozenset({"surface.py", "overlay.py"})

#: A class declaration line carrying `# base-exempt: <reason>` is a
#: deliberate, reviewed exception.
#:
#: Its own marker, not `find_inline_stylesheets`'s `token-exempt` — exactly
#: the call `kit.rectangle_card_guard` already made when it spelled its
#: escape hatch `card-exempt`: the axis here is a **base class**, not a
#: literal value, and one marker per axis keeps an exemption from silencing
#: a guard it was never reviewed against. EPIC-007A's task file asked for
#: `token-exempt` to be reused; that predates noticing `card-exempt`'s
#: precedent, and the deviation is recorded in the task file.
#:
#: Stricter than both older markers in one way: the reason is **required**,
#: not merely conventional. `token-exempt`/`card-exempt` match on presence
#: alone, so a bare marker silences them. This axis is new, so nothing
#: depends on the looser spelling, and an exemption nobody justified is how
#: a guard quietly stops meaning anything.
_BASE_EXEMPT_RE = re.compile(r"#\s*base-exempt\s*:\s*\S")

#: Same exemption convention again, for a container that genuinely means to
#: paint its descendants.
_CASCADE_EXEMPT_MARKER = "cascade-exempt"

#: The QSS properties that actually show when they leak downward. `color`
#: is left out on purpose: text colour inherits in Qt anyway, and a
#: container setting it for its labels is the normal way to do that.
_CASCADING_PROPERTIES = ("border", "background")

#: Qt widgets that hold children **without** a layout, so the layout-owner
#: check below never sees them. Missing this class of container is not
#: hypothetical: the reference app styled its `QStackedWidget` — the widget
#: holding *every screen* — with a bare property list, and the guard walked
#: straight past the largest cascade in the whole application.
_IMPLICIT_CONTAINERS = frozenset(
    {
        "QStackedWidget",
        "QTabWidget",
        "QSplitter",
        "QScrollArea",
        "QMainWindow",
        "QDockWidget",
        "QToolBar",
        "QMdiArea",
    }
)

#: Layout constructors that adopt their argument as the widget they lay out.
#: `QWidget.setLayout()` is the other way in and is matched separately.
_LAYOUT_CONSTRUCTORS = frozenset(
    {
        "QVBoxLayout",
        "QHBoxLayout",
        "QGridLayout",
        "QFormLayout",
        "QStackedLayout",
    }
)


@dataclass(frozen=True)
class InlineStylesheetFinding:
    """One hardcoded colour literal found outside `kit/style.py`."""

    file: Path
    line_number: int
    line_text: str
    matched: str


@dataclass(frozen=True)
class UnscopedContainerFinding:
    """One `setStyleSheet()` written as a bare property list on a widget that
    owns a layout — Qt's universal selector, applied to a widget with
    children to apply it to."""

    file: Path
    line_number: int
    line_text: str
    target: str
    properties: tuple[str, ...]


@dataclass(frozen=True)
class BareQtBaseFinding:
    """One `QFrame`/`QDialog`/`QWidget` subclass declared outside its base's
    own definition file — should extend `Surface`/`Overlay` instead, or say
    why not with `# base-exempt: <reason>`."""

    file: Path
    line_number: int
    line_text: str
    qt_base: str


def find_inline_stylesheets(
    root: Path,
    exempt_dirs: Iterable[Path] = (),
    colour_source_names: Iterable[str] = (),
) -> list[InlineStylesheetFinding]:
    """
    @brief Scans every `.py` file under `root` for a hardcoded colour
    literal, returning one finding per occurrence.
    @param exempt_dirs Directories excluded entirely — prefer the inline
    `token-exempt` marker for a single justified literal where possible.
    @param colour_source_names File names that legitimately *define* colours
    and so are skipped, alongside this package's own `style.py`. A consuming
    app passes its palette module here (the reference consumer:
    `("palette.py",)`).

    @details Matched by file name, not path, because that is what the
    existing `style.py` skip and `_BASE_DEFINITION_FILES` both already do —
    a second matching convention in the same module would be the more
    surprising choice. Names are exact, so a file merely containing
    "palette" is not excused.
    """
    exempt_dirs = [Path(d).resolve() for d in exempt_dirs]
    skipped_names = {_STYLE_MODULE_NAME, *colour_source_names}
    findings: list[InlineStylesheetFinding] = []

    for py_file in sorted(root.rglob("*.py")):
        if py_file.name in skipped_names:
            continue
        resolved = py_file.resolve()
        if any(_is_within(resolved, exempt) for exempt in exempt_dirs):
            continue

        for line_number, line_text in enumerate(
            py_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if _EXEMPT_MARKER in line_text:
                continue
            stripped = line_text.strip()
            if stripped.startswith("#"):
                continue
            match = _HEX_COLOR_RE.search(line_text)
            if match is not None:
                findings.append(
                    InlineStylesheetFinding(
                        file=py_file,
                        line_number=line_number,
                        line_text=line_text.strip(),
                        matched=match.group(0),
                    )
                )

    return findings


def find_bare_qt_base_widgets(
    root: Path, exempt_dirs: Iterable[Path] = ()
) -> list[BareQtBaseFinding]:
    """
    @brief Scans every `.py` file under `root` (except `surface.py`/
    `overlay.py`) for a class directly subclassing `QFrame`/`QDialog`/
    `QWidget`, returning one finding per occurrence.
    @details A class line carrying `# base-exempt: <reason>` is skipped —
    `QWidget` in particular is a legitimate base for something that is not a
    surface at all (a pure layout composite, an MVC view root), which
    `QFrame`/`QDialog` never were.
    """
    exempt_dirs = [Path(d).resolve() for d in exempt_dirs]
    findings: list[BareQtBaseFinding] = []

    for py_file in sorted(root.rglob("*.py")):
        if py_file.name in _BASE_DEFINITION_FILES:
            continue
        resolved = py_file.resolve()
        if any(_is_within(resolved, exempt) for exempt in exempt_dirs):
            continue

        for line_number, line_text in enumerate(
            py_file.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if _BASE_EXEMPT_RE.search(line_text):
                continue
            match = _BARE_QT_BASE_RE.match(line_text)
            if match is not None:
                findings.append(
                    BareQtBaseFinding(
                        file=py_file,
                        line_number=line_number,
                        line_text=line_text.strip(),
                        qt_base=match.group(1),
                    )
                )

    return findings


def find_unscoped_container_stylesheets(
    root: Path,
    exempt_dirs: Iterable[Path] = (),
) -> list[UnscopedContainerFinding]:
    """
    @brief Finds `setStyleSheet()` calls written as a bare property list on a
    widget that owns a layout.

    @details A QSS string with no selector is Qt's **universal selector**. It
    repaints every descendant that does not carry its own rule for the same
    property — so a container styled this way hands its border, its
    background and its radius to every label, field and button inside it.

    Only widgets that own a layout are reported. The same string on a leaf is
    the ordinary way to style one widget, and flagging those would bury the
    real findings under a hundred harmless ones — in the reference app, 63
    unscoped stylesheets narrow to 16 containers.

    `color` is deliberately not among the properties watched: text colour
    inherits in Qt regardless of selectors, and a container setting it once
    for its labels is idiomatic rather than a mistake.

    **Static, and therefore conservative.** Widget ownership is read from the
    source: a name passed to a layout constructor, one that gets
    `.setLayout()`, or one constructed from a Qt class that holds children
    without a layout at all (`QStackedWidget`, `QTabWidget`, `QSplitter`,
    ...). A container assembled through a helper this cannot follow
    is missed. A miss is the acceptable failure here — a guard that cries
    wolf on leaves gets switched off, and then it guards nothing.

    Mark a deliberate exception with `# cascade-exempt: <reason>` on the same
    line, same convention as the other two guards.
    """
    exempt = [directory.resolve() for directory in exempt_dirs]
    findings: list[UnscopedContainerFinding] = []

    for path in sorted(root.rglob("*.py")):
        if any(_is_within(path.resolve(), directory) for directory in exempt):
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:  # pragma: no cover — a file that cannot compile
            continue
        lines = source.splitlines()

        for scope in _scopes(tree):
            containers = _layout_owners(scope)
            findings.extend(_findings_in(scope, containers, path, lines))
    return findings


def _walk_within_scope(scope: ast.AST):
    """`ast.walk`, but it does not descend into a nested class body — that
    body is its own scope and gets visited on its own."""
    queue = list(ast.iter_child_nodes(scope))
    while queue:
        node = queue.pop()
        yield node
        if isinstance(node, ast.ClassDef):
            continue
        queue.extend(ast.iter_child_nodes(node))


def _findings_in(
    scope: ast.AST,
    containers: set[str],
    path: Path,
    lines: list[str],
) -> list[UnscopedContainerFinding]:
    findings: list[UnscopedContainerFinding] = []
    for node in _walk_within_scope(scope):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        call_target = node.func
        if (
            not isinstance(call_target, ast.Attribute)
            or call_target.attr != "setStyleSheet"
        ):
            continue
        text = "".join(_static_str_parts(node.args[0]))
        # No static text at all means the sheet is built elsewhere; a
        # `{` means it carries a selector block and scopes itself.
        if not text or "{" in text:
            continue
        properties = tuple(name for name in _CASCADING_PROPERTIES if name in text)
        if not properties:
            continue
        target = _target_name(call_target.value)
        if target not in containers:
            continue
        line_text = lines[node.lineno - 1].strip()
        if _CASCADE_EXEMPT_MARKER in line_text:
            continue
        findings.append(
            UnscopedContainerFinding(
                file=path,
                line_number=node.lineno,
                line_text=line_text,
                target=target,
                properties=properties,
            )
        )
    return findings


def _scopes(tree: ast.AST) -> list[ast.AST]:
    """Each class body, plus the module with its classes removed.

    `self` has to be resolved per class, not per file. Resolving it
    module-wide made one class that lays itself out vouch for every other
    class in the same module — which reported a leaf widget in the
    reference app that owns no layout at all. A guard's first false
    positive is how it gets switched off.
    """
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    module_only = ast.Module(
        body=[n for n in getattr(tree, "body", []) if not isinstance(n, ast.ClassDef)],
        type_ignores=[],
    )
    return [module_only, *classes]


def _layout_owners(scope: ast.AST) -> set[str]:
    """Every name in one scope handed to a layout constructor or given one
    via `setLayout()` — i.e. every widget with children to cascade onto."""
    owners: set[str] = set()
    for node in _walk_within_scope(scope):
        # `x = QStackedWidget()` — holds children with no layout involved.
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            called = node.value.func
            if isinstance(called, ast.Name) and called.id in _IMPLICIT_CONTAINERS:
                owners.update(_target_name(t) for t in node.targets)
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in _LAYOUT_CONSTRUCTORS
            and node.args
        ):
            owners.add(_target_name(node.args[0]))
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "setLayout":
            owners.add(_target_name(node.func.value))
    owners.discard("")
    return owners


def _target_name(node: ast.AST) -> str:
    """A stable name for the widget an expression refers to. Only the two
    forms that actually appear — a local `tile`, and `self._card`."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            return f"self.{node.attr}"
        return node.attr
    return ""


def _static_str_parts(node: ast.AST) -> list[str]:
    """The literal text of a string, f-string or `+` concatenation of them.

    Interpolated values are skipped rather than guessed at — a token value
    is a colour, never a selector, so dropping it cannot turn a scoped sheet
    into an unscoped one or the reverse.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        return [part for value in node.values for part in _static_str_parts(value)]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _static_str_parts(node.left) + _static_str_parts(node.right)
    return []


def _is_within(path: Path, directory: Path) -> bool:
    return directory in path.parents or path == directory


def format_inline_stylesheet_findings(findings: list[InlineStylesheetFinding]) -> str:
    lines = [f"{len(findings)} hardcoded colour literal(s) found outside kit/style.py:"]
    for finding in findings:
        lines.append(
            f"  {finding.file}:{finding.line_number}: {finding.matched}"
            f"    | {finding.line_text}"
        )
    return "\n".join(lines)


def format_bare_qt_base_findings(findings: list[BareQtBaseFinding]) -> str:
    lines = [
        (
            f"{len(findings)} bare Qt base subclass(es) found outside "
            "surface.py or overlay.py:"
        )
    ]
    for finding in findings:
        lines.append(
            f"  {finding.file}:{finding.line_number}: extends {finding.qt_base} directly"
            f"    | {finding.line_text}"
        )
    return "\n".join(lines)


def format_unscoped_container_findings(
    findings: list[UnscopedContainerFinding],
) -> str:
    lines = [
        (
            f"{len(findings)} unscoped stylesheet(s) on a widget that owns a "
            "layout — Qt reads a property list with no selector as the "
            "universal selector and repaints every child:"
        )
    ]
    for finding in findings:
        lines.append(
            f"  {finding.file}:{finding.line_number}: {finding.target} leaks "
            f"{', '.join(finding.properties)}    | {finding.line_text}"
        )
    return "\n".join(lines)
