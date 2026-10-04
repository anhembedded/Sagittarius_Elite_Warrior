"""A tag's claim about its enforcement must be true: the guard exists, the gate runs it.

Grammar: `` `[ITEM(; ITEM)*]` `` with ``ITEM := kind[: arg(, arg)*]``. Only a
bracket group whose first word is a kind is a tag, so `[chart-env]` is prose. An
argument written `<…>` is a placeholder (a legend's `[guard: <test file>]`).

- `guard`: each argument is a tracked path, or a bare `test_*.py` name that
  resolves to exactly one tracked file under `tests/`.
- `gate`: `ruff <CODE>` only when the configured selectors select CODE; any
  other step must be one `scripts/ci-local.ps1` runs.
- `review`: each argument is a Check ID of the pr-review rubric.
- `eye`: no argument. `contract`: each argument is a tracked path.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from .markdown import LineKind, classify
from .problems import Problem
from .repository import Repository
from .trees import PROMPT_TREES, collect

RUBRIC_PATH = ".claude/skills/pr-review/references/rubric.md"
CI_SCRIPT = "scripts/ci-local.ps1"

_KINDS = ("guard", "gate", "review", "eye", "contract")
_TAG = re.compile(r"`\[([^\]\n]*)\]`")
_FIRST_WORD = re.compile(r"\s*([\w-]+)")
_ITEM = re.compile(r"^(guard|gate|review|eye|contract)(?:\s*:\s*(.*))?$")
_RUBRIC_ID = re.compile(r"^\|\s*\*\*([A-N]\d+)\*\*", re.MULTILINE)
_RUFF_CODE = re.compile(r"^ruff\s+([A-Z]+[0-9]*)$")
_TEST_FILE = re.compile(r"^test_[\w-]*\.py$")
_DEFAULT_RUFF_SELECT = ("E4", "E7", "E9", "F")

#: Gate steps other than a ruff code -> (the file that runs it, the text proving it does).
GATE_STEPS: dict[str, tuple[str, str]] = {
    "mypy": (CI_SCRIPT, "Mypy"),
    "ruff format": (CI_SCRIPT, "ruff format"),
    "run-log scan": (CI_SCRIPT, "Invoke-RunLogScan"),
    "reference check": (CI_SCRIPT, "check_skill_prompt_references.py"),
    "commit lint": (".github/workflows/commit-lint.yml", "check_commit_messages.py"),
    "pre-commit hook": (".claude/settings.json", "pre_tool_use.py"),
}


def load_rubric_ids(repository: Repository) -> frozenset[str]:
    """The Check IDs (A1, M6, …) the pr-review rubric defines; empty when it is absent."""
    if not (repository.root / RUBRIC_PATH).is_file():
        return frozenset()
    return frozenset(_RUBRIC_ID.findall(repository.text(RUBRIC_PATH)))


def ruff_selectors(repository: Repository) -> tuple[frozenset[str], frozenset[str]]:
    """(selected, ignored) rule prefixes from `pyproject.toml`'s ruff configuration."""
    path = repository.root / "pyproject.toml"
    config = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    ruff = config.get("tool", {}).get("ruff", {})
    lint = {**ruff, **ruff.get("lint", {})}
    selected = set(lint.get("select", _DEFAULT_RUFF_SELECT)) | set(
        lint.get("extend-select", ())
    )
    return frozenset(selected), frozenset(lint.get("ignore", ()))


class _Context:
    """What every tag argument is checked against, read once per run."""

    def __init__(self, repository: Repository) -> None:
        self.repository = repository
        self.rubric = load_rubric_ids(repository)
        self.selected, self.ignored = ruff_selectors(repository)
        self.tests = [path for path in repository.files() if path.startswith("tests/")]

    def guard(self, arg: str) -> str | None:
        if self.repository.holds(arg):
            return None
        if not _TEST_FILE.match(arg):
            return f"guard `{arg}` is neither a tracked path nor a `test_*.py` name"
        matches = [path for path in self.tests if Path(path).name == arg]
        if len(matches) == 1:
            return None
        if not matches:
            return f"guard `{arg}` names no tracked test under tests/"
        return f"guard `{arg}` is ambiguous: {', '.join(matches)}"

    def gate(self, arg: str) -> str | None:
        code = _RUFF_CODE.match(arg)
        if code:
            rule = code.group(1)
            if any(rule.startswith(prefix) for prefix in self.ignored) or not any(
                rule.startswith(prefix) for prefix in self.selected
            ):
                return f"gate `ruff {rule}` is not selected by pyproject.toml's ruff config"
            return None
        step = GATE_STEPS.get(arg)
        if step is None:
            return f"gate `{arg}` is no step the gate runs ({', '.join(GATE_STEPS)}, ruff <CODE>)"
        runner, marker = step
        path = self.repository.root / runner
        if not path.is_file() or marker not in path.read_text(encoding="utf-8"):
            return f"gate `{arg}`: {runner} does not run it (no `{marker}`)"
        return None

    def review(self, arg: str) -> str | None:
        return (
            None
            if arg in self.rubric
            else f"review `{arg}` is no Check ID in {RUBRIC_PATH}"
        )

    def contract(self, arg: str) -> str | None:
        return (
            None
            if self.repository.holds(arg)
            else f"contract `{arg}` is not in the repository"
        )


def _item_problems(context: _Context, item: str) -> list[str]:
    parsed = _ITEM.match(item.strip())
    if parsed is None:
        return [f"malformed tag item `{item.strip()}` (expected `kind[: arg, …]`)"]
    kind, raw = parsed.group(1), parsed.group(2)
    args = [arg.strip() for arg in raw.split(",")] if raw is not None else []
    if kind == "eye":
        return ["`eye` takes no argument"] if args else []
    if not args or not all(args):
        return [f"`{kind}` needs an argument"]
    checker = {
        "guard": context.guard,
        "gate": context.gate,
        "review": context.review,
        "contract": context.contract,
    }[kind]
    found = (
        checker(arg) for arg in args if not (arg.startswith("<") and arg.endswith(">"))
    )
    return [problem for problem in found if problem is not None]


def tag_problems(context: _Context, line: str) -> list[str]:
    problems: list[str] = []
    for tag in _TAG.finditer(line):
        first = _FIRST_WORD.match(tag.group(1))
        if first is None or first.group(1) not in _KINDS:
            continue
        for item in tag.group(1).split(";"):
            problems.extend(_item_problems(context, item))
    return problems


def check_tag_grammar(repository: Repository) -> list[Problem]:
    context = _Context(repository)
    root = repository.root
    problems: list[Problem] = []
    for source in collect(root, PROMPT_TREES):
        relative = source.relative_to(root).as_posix()
        for line in classify(source.read_text(encoding="utf-8")):
            if line.kind is LineKind.CODE:
                continue
            for message in tag_problems(context, line.text):
                problems.append(Problem("tag grammar", relative, line.number, message))
    return problems
