"""
Guards two Application-layer naming/placement conventions:

- CQRS structure (.agents/rules/code-rule.md rule 8): every Command/Query/
  Handler class lives under application/use_cases/, one file per role
  (command.py, query.py, handler.py).
- Explicit abstractions (.agents/rules/code-rule.md rule 2): every interface
  class (name starts with `I` + uppercase, e.g. IMarketDataRepository) lives
  under application/ports/, in a file named `i_*.py`.

Pure static analysis (ast) — no PySide6/DB import, no qapp fixture needed.
"""

import ast
from pathlib import Path

_APPLICATION_ROOT = Path(__file__).resolve().parents[3] / "src" / "application"
_USE_CASES_DIR = _APPLICATION_ROOT / "use_cases"
_PORTS_DIR = _APPLICATION_ROOT / "ports"


def _iter_python_files(root: Path):
    for path in root.rglob("*.py"):
        if "__pycache__" not in path.parts:
            yield path


def _class_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def _cqrs_expected_filename(class_name: str) -> str | None:
    # ICommandHandler/IQueryHandler are the abstract Protocols in ports/, not
    # concrete use-case classes — the interface-name check excludes them.
    if _is_interface_name(class_name):
        return None
    if class_name.endswith("CommandHandler") or class_name.endswith("QueryHandler"):
        return "handler.py"
    if class_name.endswith("Command"):
        return "command.py"
    if class_name.endswith("Query"):
        return "query.py"
    return None


def _is_interface_name(class_name: str) -> bool:
    return len(class_name) > 1 and class_name[0] == "I" and class_name[1].isupper()


def test_cqrs_classes_live_under_use_cases_dir():
    offenders = []
    for path in _iter_python_files(_APPLICATION_ROOT):
        if _USE_CASES_DIR in path.parents:
            continue
        for name in _class_names(path):
            if _cqrs_expected_filename(name) is not None:
                offenders.append(path)
                break

    assert offenders == [], (
        f"Command/Query/Handler classes found outside {_USE_CASES_DIR}: "
        f"{[str(p) for p in offenders]}"
    )


def test_cqrs_files_match_command_query_handler_naming():
    offenders = []
    for path in _iter_python_files(_USE_CASES_DIR):
        for name in _class_names(path):
            expected = _cqrs_expected_filename(name)
            if expected is not None and path.name != expected:
                offenders.append(path)
                break

    assert offenders == [], (
        "Command/Query/Handler files must be named command.py/query.py/"
        f"handler.py: {[str(p) for p in offenders]}"
    )


def test_interface_classes_live_under_ports_dir():
    offenders = []
    for path in _iter_python_files(_APPLICATION_ROOT):
        if _PORTS_DIR in path.parents:
            continue
        if any(_is_interface_name(name) for name in _class_names(path)):
            offenders.append(path)

    assert offenders == [], (
        f"Interface classes (IXxx) found outside {_PORTS_DIR}: "
        f"{[str(p) for p in offenders]}"
    )


def test_interface_files_use_i_prefix_naming():
    offenders = []
    for path in _iter_python_files(_PORTS_DIR):
        has_interface = any(_is_interface_name(name) for name in _class_names(path))
        if has_interface and not path.stem.startswith("i_"):
            offenders.append(path)

    assert offenders == [], (
        f"Interface files under {_PORTS_DIR} must be named 'i_*.py': "
        f"{[str(p) for p in offenders]}"
    )
