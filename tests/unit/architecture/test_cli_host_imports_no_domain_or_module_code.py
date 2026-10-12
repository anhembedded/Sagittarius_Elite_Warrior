"""Guard: the command-line host imports no domain or module code (`EPIC-038B`, decision D7).

**Why this exists.** The host half of the command line — the exit-status
mapping, the report-renderer registry and the renderers (`src/support/cli_host/`)
— is built in this application so that `EPIC-038C`..`J` can use it today, and
is meant to move to the Engine later as one package move. A host that learned
one trading symbol, one bot state or one domain value object could not move: it
would drag the application with it. The boundary rules already say a support
package imports no module; this guard says the rest, and says it as an
allowlist, so the question "may the host import X" is answered by a list a
reviewer reads, not by the absence of a rule.

**What it allows.** In `src/support/cli_host/**`, an import must be one of:
the Python standard library; the package itself; or one of the four kernel
contract files below, which are the host's vocabulary (what an outcome is, what
a report is, what a renderer is) and would move with it. Everything else —
`src/modules`, `src/core/vo`, `src/infrastructure`, `src/shell`,
`src/presentation`, another support package, the Engine, a third-party package —
fails, naming the file and line.

**What it does not read.** A dynamic import (`importlib.import_module`) is
invisible to an AST scan; the package has none, and the runtime half of the
promise is that `tests/unit/support/cli_host/` imports and runs the host with no
application object graph.

Mutation check (run, not described): `test_planting_a_forbidden_import_is_caught`
runs the scanner over a real host file with one import planted in it, for each
kind of forbidden import.

Stdlib only: no Qt, no Engine.

Retire when: the host has moved to the Engine, where Engine rules govern it.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACKAGE = _REPO_ROOT.name
_HOST_ROOT = _REPO_ROOT / "src" / "support" / "cli_host"
_HOST_MODULE = f"{_PACKAGE}.src.support.cli_host"

#: The host's vocabulary, which moves with it. Four files, named.
_ALLOWED_KERNEL_CONTRACTS = frozenset(
    f"{_PACKAGE}.src.core.contracts.{name}"
    for name in (
        "cli_outcome",
        "report",
        "i_report_renderer",
        "i_report_formats",
    )
)

#: A walk that finds fewer files than this lost its subject.
_MINIMUM_FILES = 8


@dataclass(frozen=True)
class _Violation:
    file: str
    line: int
    module: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line} imports {self.module}"


def _is_standard_library(module: str) -> bool:
    return module.split(".")[0] in sys.stdlib_module_names


def _is_allowed(module: str) -> bool:
    if module == _HOST_MODULE or module.startswith(_HOST_MODULE + "."):
        return True
    if module in _ALLOWED_KERNEL_CONTRACTS:
        return True
    return _is_standard_library(module)


def scan_source(source: str, file: str) -> list[_Violation]:
    """Every import in `source` (module level or not) that the host may not make."""
    violations: list[_Violation] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                # A relative import stays inside the package unless it climbs out
                # of it; the host is `src/support/cli_host/<one level>/<file>`.
                if node.level > _relative_depth(file):
                    violations.append(
                        _Violation(
                            file, node.lineno, "." * node.level + (node.module or "")
                        )
                    )
                continue
            # `from a.b import c` imports `a.b`, and `c` may itself be a module of
            # the kernel. Allowed when `a.b` is, or when *every* name is: one
            # allowed name must never excuse a forbidden one beside it.
            module = node.module or ""
            if _is_allowed(module):
                continue
            violations.extend(
                _Violation(file, node.lineno, f"{module}.{alias.name}")
                for alias in node.names
                if not _is_allowed(f"{module}.{alias.name}")
            )
            continue
        else:
            continue
        violations.extend(
            _Violation(file, node.lineno, name)
            for name in names
            if not _is_allowed(name)
        )
    return violations


def _relative_depth(file: str) -> int:
    """How many dots stay inside the host: 1 for a file at its root, 2 one level down."""
    parts = Path(file).parts
    return len(parts) - parts.index("cli_host") - 1


def _host_files() -> list[Path]:
    return sorted(p for p in _HOST_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def test_the_host_imports_no_domain_or_module_code() -> None:
    files = _host_files()
    assert len(files) >= _MINIMUM_FILES, "the scan found too few files to mean anything"

    found = [
        violation
        for path in files
        for violation in scan_source(
            path.read_text(encoding="utf-8"), str(path.relative_to(_REPO_ROOT))
        )
    ]

    assert not found, "the CLI host reached outside its boundary:\n" + "\n".join(
        str(v) for v in found
    )


_PLANTED = {
    "a module": f"import {_PACKAGE}.src.modules.trading.contracts.order",
    "a module, from-form": f"from {_PACKAGE}.src.modules.bots.contracts import x",
    "a domain value object": f"from {_PACKAGE}.src.core.vo.timeframe import TimeFrame",
    "another kernel contract": f"from {_PACKAGE}.src.core.contracts.i_cli_registry import ICliRegistry",
    "the shell": f"from {_PACKAGE}.src.shell.composition_root import create_app",
    "presentation": f"from {_PACKAGE}.src.presentation.cli.cli_parser import build_parser",
    "infrastructure": f"import {_PACKAGE}.src.infrastructure.engine_adapters",
    "another support package": f"from {_PACKAGE}.src.support.binance_gateway import x",
    "the Engine": "from sagittarius_engine import App",
    "a third-party package": "import binance",
    "a relative import out of the package": "from ... import modules",
    "a mixed import of an allowed and a forbidden contract": (
        f"from {_PACKAGE}.src.core.contracts import cli_outcome, i_cli_registry"
    ),
    "a forbidden contract first, an allowed one second": (
        f"from {_PACKAGE}.src.core.contracts import i_cli_registry, cli_outcome"
    ),
}


@pytest.mark.parametrize("kind", sorted(_PLANTED))
def test_planting_a_forbidden_import_is_caught(kind: str) -> None:
    """The mutation proof: the scanner, run over a real host file with one
    forbidden import planted in it, names that line. Without this the guard
    could pass because it checks nothing."""
    path = _HOST_ROOT / "adapters" / "text_report_renderer.py"
    source = path.read_text(encoding="utf-8") + "\n" + _PLANTED[kind] + "\n"

    found = scan_source(source, str(path.relative_to(_REPO_ROOT)))

    assert len(found) == 1, kind
    assert found[0].line == source.count("\n"), kind


@pytest.mark.parametrize(
    "statement",
    [
        "import json",
        "from collections.abc import Callable",
        f"from {_PACKAGE}.src.core.contracts.cli_outcome import CliOutcome",
        f"from {_PACKAGE}.src.core.contracts.report import Report",
        f"from {_PACKAGE}.src.core.contracts import cli_outcome, report",
        f"from {_PACKAGE}.src.support.cli_host.report_formats import ReportFormats",
        "from .json_report_renderer import JsonReportRenderer",
    ],
)
def test_the_allowed_imports_are_not_flagged(statement: str) -> None:
    path = _HOST_ROOT / "adapters" / "text_report_renderer.py"

    assert scan_source(statement + "\n", str(path.relative_to(_REPO_ROOT))) == []
