"""The scan `test_ui_reaches_the_application_through_its_doors.py` (`EPIC-048A`) reads the UI tree
with: every import a `src/modules/*/ui/` file makes that goes around the UI's doors, and every
function under `ui/` that takes the whole `IContainer`.

The method is De-risk R7's (`Tasks/epics/EPIC-047_vps_bots_tab/DERISK.md` §7.2), `ast` plus
`importlib`, with one addition: a relative import is resolved against the file's own package before
it is classified, so `from ...application.services import x` cannot slip past a scan that reads only
absolute imports. The allowlist is not written here: it is read from the rule's own line in
`.claude/rules/architecture-rule.md` §3.1, the one place it is named (`P3`).

Split from the guard so each file stays under `architecture-rule.md` §5.4's 400-line threshold and
the guard reads as its assertions.
"""

from __future__ import annotations

import ast
import dataclasses
import enum
import importlib
import inspect
import re
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import ModuleType


def _repo_root() -> Path:
    """By landmark (`test_no_root_is_found_by_counting.py`)."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError("no pyproject.toml above this file")


REPO_ROOT = _repo_root()
MODULES_ROOT = REPO_ROOT / "src" / "modules"
RULE_FILE = REPO_ROOT / ".claude" / "rules" / "architecture-rule.md"
PACKAGE = REPO_ROOT.name

#: The rule's allowlist line: the bullet under §3.1 that opens with this text names every port a UI
#: file may hold, each in backticks.
ALLOWLIST_LINE_PREFIX = "- **The doors and the allowlist.**"

#: A use case's own message module: a query, a command or a result is how the UI talks through the
#: dispatcher, so it is not an application internal (R7 §7.2, step 2).
USE_CASE_MESSAGE = re.compile(
    r"\.application\.(queries|commands|use_cases)\.[a-z_0-9]+(\.(query|command|result))?$"
)

APP_SERVICE = "APP_SERVICE"
APP_OTHER = "APP_OTHER"
ADAPTER = "ADAPTER"
PORT = "PORT"
#: The function count's own key in an area's counts.
CONTAINER = "CONTAINER"
FN = "fn"
DATA = "data"


@dataclass(frozen=True)
class Hit:
    """One import around the doors, or one function that takes the container."""

    area: str
    path: str
    name: str
    kind: str

    def __str__(self) -> str:
        return f"{self.path}: {self.name} ({self.kind})"


def allowlist() -> frozenset[str]:
    """The ports the rule lets a UI file hold, read from the rule's own line."""
    for line in RULE_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(ALLOWLIST_LINE_PREFIX):
            return frozenset(re.findall(r"`(I[A-Za-z0-9]+)`", line))
    return frozenset()


def ui_files() -> list[Path]:
    """Every `.py` under each module's `ui/`."""
    return sorted(
        p for p in MODULES_ROOT.glob("*/ui/**/*.py") if "__pycache__" not in p.parts
    )


def area_of(path: Path) -> str:
    """`<m>/ui/<first directory>`; a file directly under `ui/` is in `<m>/ui`."""
    parts = path.relative_to(MODULES_ROOT).parts
    return "/".join(parts[:3]) if len(parts) > 3 else "/".join(parts[:2])


def _dotted(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT).with_suffix("")
    parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
    return ".".join((PACKAGE, *parts))


def _package_of(path: Path) -> str:
    dotted = _dotted(path)
    return dotted if path.name == "__init__.py" else dotted.rpartition(".")[0]


def imports_of(path: Path) -> list[tuple[str, str | None]]:
    """`(module, name)` per imported name, relative imports resolved; `name` is `None` for
    `import module`."""
    found: list[tuple[str, str | None]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.extend((alias.name, None) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = _package_of(path).split(".")
                anchor = ".".join(base[: len(base) - node.level + 1])
                module = f"{anchor}.{node.module}" if node.module else anchor
            else:
                module = node.module or ""
            found.extend((module, alias.name) for alias in node.names)
    return found


@cache
def _module(name: str) -> ModuleType:
    return importlib.import_module(name)


def _resolve(module: str, name: str | None) -> object:
    if name is None:
        return _module(module)
    owner = _module(module)
    if hasattr(owner, name):
        return getattr(owner, name)
    return _module(f"{module}.{name}")


def classify(module: str, name: str | None, allowed: frozenset[str]) -> str | None:
    """R7 §7.2 step 2: the class of one imported name, or `None` when it goes through the doors."""
    short = module.removeprefix(PACKAGE + ".")
    if not short.startswith("src."):
        return None
    if ".application.services." in short or short.endswith(".application.services"):
        return APP_SERVICE
    if (
        ".adapters." in short
        or short.endswith(".adapters")
        or short.startswith("src.infrastructure")
    ):
        return ADAPTER
    if ".application." in short and not USE_CASE_MESSAGE.search(short):
        return APP_OTHER
    if name and ".contracts" in short and name not in allowed:
        obj = _resolve(module, name)
        if inspect.isclass(obj) and getattr(obj, "__abstractmethods__", None):
            return PORT
    return None


def fn_or_data(module: str, name: str | None) -> str:
    """R7 §7.2 step 3: computation the UI runs, or a value (a dataclass, an enum, a constant, or an
    exception the UI only catches, as R7 counted it)."""
    obj = _resolve(module, name)
    if inspect.isclass(obj):
        is_value = dataclasses.is_dataclass(obj) or issubclass(
            obj, (enum.Enum, BaseException)
        )
        return DATA if is_value else FN
    return FN if callable(obj) or inspect.ismodule(obj) else DATA


def _annotation_names_container(annotation: ast.expr | None) -> bool:
    return annotation is not None and "IContainer" in ast.unparse(annotation)


def container_functions(path: Path) -> list[str]:
    """R7 §7.2 step 4: each function with a parameter annotated `IContainer`; for `__init__`, its
    class."""
    found: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    classes = {
        id(item): node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        for item in node.body
    }
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if any(_annotation_names_container(param.annotation) for param in params):
            found.append(
                classes.get(id(node), node.name)
                if node.name == "__init__"
                else node.name
            )
    return found


def scan() -> list[Hit]:
    """Every hit in the UI tree, keyed by area and by the class the baseline counts."""
    allowed = allowlist()
    hits: list[Hit] = []
    for path in ui_files():
        area = area_of(path)
        shown = path.relative_to(REPO_ROOT).as_posix()
        for module, name in imports_of(path):
            kind = classify(module, name, allowed)
            if kind is None:
                continue
            if kind in (APP_SERVICE, APP_OTHER):
                kind = f"{kind}_{fn_or_data(module, name)}"
            hits.append(Hit(area, shown, f"{module}.{name}" if name else module, kind))
        hits.extend(
            Hit(area, shown, function, CONTAINER)
            for function in container_functions(path)
        )
    return hits


def counts(hits: list[Hit]) -> dict[str, dict[str, int]]:
    """`{area: {kind: count}}`, the shape of the baseline file."""
    per_area: dict[str, Counter[str]] = {}
    for hit in hits:
        per_area.setdefault(hit.area, Counter())[hit.kind] += 1
    return {area: dict(sorted(per_area[area].items())) for area in sorted(per_area)}


#: The baseline file's three sections (ADR D4): imports around the doors that run computation, hold
#: a behavioural port or reach an adapter; imports of application data; and container-taking
#: functions.
AROUND_THE_DOORS = "around_the_doors"
APPLICATION_DATA = "application_data"
TAKES_THE_CONTAINER = "takes_the_container"


def section_of(kind: str) -> str:
    if kind == CONTAINER:
        return TAKES_THE_CONTAINER
    return APPLICATION_DATA if kind.endswith(f"_{DATA}") else AROUND_THE_DOORS


def baseline_shape(hits: list[Hit]) -> dict[str, dict[str, dict[str, int]]]:
    """The measured counts in the baseline file's shape: `{section: {area: {kind: count}}}`."""
    shaped: dict[str, dict[str, dict[str, int]]] = {
        AROUND_THE_DOORS: {},
        APPLICATION_DATA: {},
        TAKES_THE_CONTAINER: {},
    }
    for area, per_kind in counts(hits).items():
        for kind, count in per_kind.items():
            shaped[section_of(kind)].setdefault(area, {})[kind] = count
    return shaped
