"""Guard: every logger in src/ must reach StdLogger's handlers.

`StdLogger` (sagittarius_engine) attaches its console/file/viewer handlers to
the `"App"` logger and sets `propagate = False` on it. Nothing is attached to
the root logger. A module that calls `logging.getLogger(__name__)` therefore
produces a logger with no handler anywhere in its chain: `logger.info(...)`
emits absolutely nothing, and only Python's last-resort fallback shows
WARNING and above, unformatted.

This is silent by construction — the code looks correct, the call succeeds,
and the message simply never appears. It cost a full reproduce-and-send-log
cycle during BUG-009, where diagnostics were added to chase a rendering
defect and the resulting log came back with none of them in it.

The check is an AST scan rather than an import-and-inspect so it stays
deterministic and needs no Qt/DB side effects from importing UI modules.
"""

import ast
from pathlib import Path

import pytest

#: Handlers live on "App"; children propagate up into it.
_REQUIRED_LOGGER_ROOT = "App"

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


#: `getLogger(name).addHandler(...)` and friends manage a logger someone else
#: owns — the name is legitimately dynamic there (see
#: data_management/signal_log_handler.py, which attaches a Qt-signal handler
#: to a caller-supplied logger). Only loggers used to *emit* are in scope.
_HANDLER_MANAGEMENT_METHODS = frozenset(
    {"addHandler", "removeHandler", "setLevel", "handlers"}
)


def _handler_management_receivers(tree: ast.AST) -> set[int]:
    """Ids of getLogger calls that are only used to attach/detach handlers."""
    receivers: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if node.attr not in _HANDLER_MANAGEMENT_METHODS:
            continue
        if isinstance(node.value, ast.Call):
            receivers.add(id(node.value))
    return receivers


def _logger_name_arguments(tree: ast.AST) -> list[tuple[int, str | None]]:
    """Returns (line number, literal name) for every logging.getLogger call.

    A name of None means the argument was not a plain string literal — for
    example `getLogger(__name__)`, which is exactly the failure mode here.
    """
    exempt = _handler_management_receivers(tree)
    found: list[tuple[int, str | None]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Attribute) or function.attr != "getLogger":
            continue
        if id(node) in exempt:
            continue
        if not node.args:
            found.append((node.lineno, None))
            continue
        first_argument = node.args[0]
        if isinstance(first_argument, ast.Constant) and isinstance(
            first_argument.value, str
        ):
            found.append((node.lineno, first_argument.value))
        else:
            found.append((node.lineno, None))
    return found


def _python_sources() -> list[Path]:
    return sorted(
        path for path in _SRC_ROOT.rglob("*.py") if "__pycache__" not in path.parts
    )


def test_source_tree_is_present():
    """Fails loudly if the scan target moved, instead of passing vacuously."""
    assert _SRC_ROOT.is_dir()
    assert _python_sources()


@pytest.mark.parametrize("source_path", _python_sources(), ids=lambda path: path.name)
def test_every_logger_is_under_the_app_namespace(source_path: Path):
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

    offenders = []
    for line_number, name in _logger_name_arguments(tree):
        if name is None:
            offenders.append(
                f"{source_path.name}:{line_number} uses a non-literal logger "
                "name (e.g. __name__)"
            )
        elif name != _REQUIRED_LOGGER_ROOT and not name.startswith(
            f"{_REQUIRED_LOGGER_ROOT}."
        ):
            offenders.append(f"{source_path.name}:{line_number} logs to {name!r}")

    assert not offenders, (
        "These loggers cannot reach StdLogger's handlers, so anything they log "
        "below WARNING is silently discarded. Use "
        f'logging.getLogger("{_REQUIRED_LOGGER_ROOT}.<Component>") instead:\n  '
        + "\n  ".join(offenders)
    )
