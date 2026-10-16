"""Guard: a module's design cites code by path and symbol, never by line, and every
symbol it names still exists.

**Why this exists.** A design document under `Docs/MODULES/` is true of
`master-warrior`, so every citation in it must stay true while the code moves.
A line number moves with every unrelated edit above it: the `alerting` migration
(`EPIC-041J`) found 11 of 139 `file:line` citations wrong on the commit that had
written them, and the owner ruled on 2026-10-16 that a design cites a path and a
symbol (a class, a function, a constant, an enum member) instead. A symbol
changes only when the code really changes, which is when the design should be
read again (`DECISION_2026-10-16_cite_code_by_symbol.md`, D1).

Two checks, each the half the other leaves open:

1. **No line citation** in any file under `Docs/MODULES/`: `x.py:12`,
   `x.py:12-30`, `x.py:41,55`, `x.py#L12`, the same on any other file
   (`sew-run.service:48`), or a bare `` `:56-72` `` continuing the previous
   citation.
2. **Every cited file and symbol exists.** Every backticked `.py` path must
   name a file: exactly one when it has a directory, at least one when it is a
   bare file name (`handler.py` is often meant as one of several). A symbol
   is checked when it is written `` `<path>.py` → `<symbol>` ``, optionally
   followed by more symbols of the same file (`` , `<symbol>` ``): the path
   resolves to exactly one file under `src/`, `scripts/` or `tests/` (a leading
   `.../` is dropped and the rest matched as a path suffix); each dotted part of the symbol (`AlertHub.publish`, a trailing
   `()` ignored) must be defined somewhere in that file's AST: a class, a
   function, or an assigned name. A renamed or deleted function turns this red,
   so a name citation cannot rot silently the way a line did.

The check is deliberately simple (the owner's brief): a name defined anywhere in
the file is enough; it does not prove `publish` is a method *of* `AlertHub`.
Point-in-time records (bug reports, decision records, case studies, task notes)
are out of scope: they may keep `file:line` at a named commit sha
(`commit-rule.md` §1, "Citing code").

Stdlib only, like the other document guards here: it must run without Qt or the
engine installed.

Retire when: module designs move out of `Docs/MODULES/`, or a documentation
tool that resolves code references itself (with the same failure on a missing
symbol) replaces these hand-written citations.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from functools import cache
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODULE_DOCS = _REPO_ROOT / "Docs" / "MODULES"
_SRC = _REPO_ROOT / "src"
_SCRIPTS = _REPO_ROOT / "scripts"
_TESTS = _REPO_ROOT / "tests"

#: The extensions a design may cite a file by. Named, rather than any `.<word>`,
#: so a host and port (`localhost.local:8080`) is not taken for a line.
_EXTENSIONS = (
    r"(?:py|pyi|ps1|psm1|sh|service|timer|toml|ini|cfg|json|ya?ml|puml|md|txt|qml|sql)"
)
#: A cited file's name, its closing backtick optional: `x.py`, `` `x.py` ``.
_FILE = r"\." + _EXTENSIONS + r"(?![A-Za-z0-9])`?"

#: A line citation, in every form a reader would recognise as one: `x.py:12`,
#: `x.py:12-30`, `x.py:41,55`, `` `x.py`:12 ``, `x.py: 12`, `x.py:L12`, `x.py#L12`,
#: `` `x.py` (L12) ``, `` `x.py` line 12 ``, the same on any other cited file
#: (`sew-run.service:48`), or a bare `` `:56-72` `` that continues the citation
#: before it.
_LINE_CITATION = re.compile(
    _FILE + r"(?:\s*:\s*L?\d+|#L\d+|\s*\(\s*L\d+|\s+lines?\s+\d+)"
    r"|`:L?\d+(?:[-,]\d+)*`"
)

#: A backticked repository path to a Python file, cited with or without a symbol.
_CITED_PATH = re.compile(r"`([A-Za-z0-9_.-]*(?:/[A-Za-z0-9_.-]+)*\.py)`")

#: `` `<path>.py` → `<symbol>` `` and any further `` , `<symbol>` `` of the same
#: file. Group 1 is the path, group 2 the run of backticked symbols.
_SYMBOL_CITATION = re.compile(
    r"`([A-Za-z0-9_./-]+\.py)`\s*→\s*(`[^`]+`(?:\s*,\s*`[^`]+`)*)"
)
_BACKTICKED = re.compile(r"`([^`]+)`")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def line_citations(text: str) -> list[tuple[int, str]]:
    """Every line citation in `text`, as (line number, the matched text)."""
    return [
        (number, match.group(0))
        for number, line in enumerate(text.splitlines(), start=1)
        for match in _LINE_CITATION.finditer(line)
    ]


def symbol_citations(text: str) -> list[tuple[str, str]]:
    """Every (path, symbol) pair `text` cites in the arrow form."""
    pairs: list[tuple[str, str]] = []
    for match in _SYMBOL_CITATION.finditer(text):
        for symbol in _BACKTICKED.findall(match.group(2)):
            pairs.append((match.group(1), symbol))
    return pairs


def defined_names(source: str) -> set[str]:
    """Every class, function and assigned name defined anywhere in `source`."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(_target_names(node.targets))
        elif isinstance(node, ast.AnnAssign | ast.AugAssign):
            names.update(_target_names([node.target]))
    return names


def _target_names(targets: Iterable[ast.expr]) -> set[str]:
    names: set[str] = set()
    for target in targets:
        for node in ast.walk(target):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                names.add(node.attr)
    return names


def resolve(cited: str, files: Iterable[Path], root: Path) -> list[Path]:
    """The files whose repository path ends with `cited` on a path boundary."""
    suffix = cited.removeprefix(".../").lstrip("/")
    name = suffix.rsplit("/", 1)[-1]
    return [
        path
        for path in files
        if path.name == name
        and (
            (relative := path.relative_to(root).as_posix()) == suffix
            or relative.endswith("/" + suffix)
        )
    ]


@cache
def _names_in(path: Path) -> frozenset[str]:
    return frozenset(defined_names(path.read_text(encoding="utf-8")))


def symbol_problems(text: str, files: Iterable[Path], root: Path) -> list[str]:
    """Why each arrow citation in `text` does not hold, if it does not."""
    candidates = tuple(files)
    problems: list[str] = []
    for cited, symbol in symbol_citations(text):
        matches = resolve(cited, candidates, root)
        if len(matches) != 1:
            found = ", ".join(p.relative_to(root).as_posix() for p in matches)
            problems.append(
                f"`{cited}` names {len(matches)} files, not one ({found or 'none'})"
            )
            continue
        parts = symbol.removesuffix("()").split(".")
        if not all(_IDENTIFIER.match(part) for part in parts):
            problems.append(f"`{cited}` → `{symbol}`: not a dotted Python name")
            continue
        names = _names_in(matches[0])
        missing = [part for part in parts if part not in names]
        if missing:
            problems.append(
                f"`{cited}` → `{symbol}`: {', '.join(missing)} is not defined in "
                f"{matches[0].relative_to(root).as_posix()}"
            )
    return problems


def path_problems(text: str, files: Iterable[Path], root: Path) -> list[str]:
    """Why each backticked `.py` path in `text` names no file, if it names none.

    A path with a directory (`alerting/module.py`) must name exactly one file; a
    bare file name (`module.py`, `handler.py`) is often meant as one of several,
    so it must name at least one. Either way a renamed or deleted file is caught.
    """
    candidates = tuple(files)
    problems: list[str] = []
    for cited in sorted(set(_CITED_PATH.findall(text))):
        found = len(resolve(cited, candidates, root))
        if found == 0 or ("/" in cited.removeprefix(".../") and found > 1):
            problems.append(f"`{cited}` names {found} files")
    return problems


def _design_files() -> list[Path]:
    return sorted(p for p in _MODULE_DOCS.rglob("*") if p.is_file())


@cache
def _source_files() -> tuple[Path, ...]:
    return tuple(
        sorted([*_SRC.rglob("*.py"), *_SCRIPTS.rglob("*.py"), *_TESTS.rglob("*.py")])
    )


def test_there_are_designs_to_check() -> None:
    assert [p for p in _design_files() if p.suffix == ".md"], (
        f"no design under {_MODULE_DOCS}: retarget this guard or retire it"
    )
    assert any(
        symbol_citations(p.read_text(encoding="utf-8"))
        for p in _design_files()
        if p.suffix == ".md"
    ), "no design cites a symbol: the existence check below would check nothing"


@pytest.mark.parametrize(
    "design", _design_files(), ids=lambda p: p.relative_to(_MODULE_DOCS).as_posix()
)
def test_a_design_cites_no_line_number(design: Path) -> None:
    found = line_citations(design.read_text(encoding="utf-8"))

    assert found == [], (
        f"{design.relative_to(_REPO_ROOT).as_posix()} cites code by line; cite the "
        f"path and the symbol instead (`<path>.py` → `<symbol>`): {found}"
    )


@pytest.mark.parametrize(
    "design",
    [p for p in _design_files() if p.suffix == ".md"],
    ids=lambda p: p.relative_to(_MODULE_DOCS).as_posix(),
)
def test_every_cited_symbol_exists(design: Path) -> None:
    text = design.read_text(encoding="utf-8")
    problems = [
        *path_problems(text, _source_files(), _REPO_ROOT),
        *symbol_problems(text, _source_files(), _REPO_ROOT),
    ]

    assert problems == [], (
        f"{design.relative_to(_REPO_ROOT).as_posix()} cites what the code does not "
        f"hold: {problems}"
    )


# --- Probes: each goes red if the check above is weakened. ---


@pytest.mark.parametrize(
    "planted",
    [
        "`alerting/module.py:83`",
        "(`grid_facts.py:190-232`)",
        "`src/shell/modules.py:41,55`",
        "`threaded_delivery_host.py:33-34`, `:56-72`",
        "see `x.py#L12`",
        "(`deploy/linux/sew-run.service:48`)",
        "`x.py:L12`",
        "`x.py`:12",
        "`x.py`: 12",
        "`x.py` (L12)",
        "`x.py` line 12",
        "`x.py` lines 12-30",
        "`run.ps1`:7",
        "and `:L56`",
    ],
)
def test_the_line_check_catches_every_form(planted: str) -> None:
    assert line_citations(f"Some text {planted} more.\n") != []


@pytest.mark.parametrize(
    "prose",
    [
        "`alerting/module.py` → `AlertingModule.dependencies`",
        "the host `localhost.local:8080` answers",
        "the level label L6 · range top",
        "`grid.md` lists 12 states",
    ],
)
def test_the_line_check_leaves_other_text_alone(prose: str) -> None:
    assert line_citations(prose) == []


def _planted_repository(tmp_path: Path) -> list[Path]:
    package = tmp_path / "src" / "modules" / "alerting" / "application"
    package.mkdir(parents=True)
    (package / "alert_hub.py").write_text(
        "LIMIT = 3\n\n"
        "class AlertHub:\n"
        "    def publish(self) -> None:\n"
        "        self.sent = True\n",
        encoding="utf-8",
    )
    other = tmp_path / "src" / "modules" / "bots" / "application"
    other.mkdir(parents=True)
    (other / "alert_hub.py").write_text("class Other: ...\n", encoding="utf-8")
    return sorted((tmp_path / "src").rglob("*.py"))


@pytest.mark.parametrize(
    "citation",
    [
        "`alerting/application/alert_hub.py` → `AlertHub`",
        "`alerting/application/alert_hub.py` → `AlertHub.publish()`",
        "`.../alerting/application/alert_hub.py` → `LIMIT`, `AlertHub.sent`",
    ],
)
def test_a_present_symbol_passes(tmp_path: Path, citation: str) -> None:
    files = _planted_repository(tmp_path)

    assert symbol_problems(citation, files, tmp_path) == []


def test_a_bare_path_that_names_no_file_is_caught(tmp_path: Path) -> None:
    files = _planted_repository(tmp_path)

    assert path_problems("`alerting/application/gone.py`", files, tmp_path) != []
    assert path_problems("`gone.py`", files, tmp_path) != []


def test_a_bare_path_is_held_to_one_file_only_when_it_has_a_directory(
    tmp_path: Path,
) -> None:
    files = _planted_repository(tmp_path)

    assert path_problems("`alert_hub.py`", files, tmp_path) == []
    assert path_problems("`application/alert_hub.py`", files, tmp_path) != []
    assert path_problems("`alerting/application/alert_hub.py`", files, tmp_path) == []


@pytest.mark.parametrize(
    ("citation", "reason"),
    [
        ("`alerting/application/alert_hub.py` → `AlertRouter`", "renamed class"),
        ("`alerting/application/alert_hub.py` → `AlertHub.deliver`", "deleted method"),
        ("`alerting/application/alert_hub.py` → `LIMIT`, `GONE`", "second symbol"),
        ("`application/alert_hub.py` → `AlertHub`", "ambiguous path"),
        ("`alerting/application/no_such.py` → `AlertHub`", "missing file"),
        ("`alerting/application/alert_hub.py` → `AlertHub(x)`", "not a name"),
    ],
)
def test_a_missing_symbol_or_file_is_caught(
    tmp_path: Path, citation: str, reason: str
) -> None:
    files = _planted_repository(tmp_path)

    assert symbol_problems(citation, files, tmp_path) != [], reason
