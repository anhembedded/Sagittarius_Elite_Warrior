"""
Guards the two conventions that make custom indicator scripts safe to add
(BOT-032). Pure static analysis (ast/glob) — no PySide6 import, no qapp,
matching test_application_layer_structure.py / test_card_layer_structure.py.
"""

import ast
from pathlib import Path

_BOT_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = _BOT_ROOT / "src" / "domain" / "indicator_scripts"
_DOMAIN_DIR = _BOT_ROOT / "src" / "domain"
_MODULE_FILE = _BOT_ROOT / "src" / "binance_bot_module.py"

#: A domain script must never reach for a UI toolkit or the engine — that is
#: what keeps PlottedLine.color a plain hex string instead of a QColor.
_FORBIDDEN_DOMAIN_IMPORTS = ("PySide6", "pyqtgraph", "sagittarius_engine")

#: The Shared Kernel: the only two engine symbols `code-rule.md` §5 permits in
#: `src/domain/` and `src/application/`. Domain events inherit `BaseEvent` so
#: the engine's `EventRegistry` can catalog them and its planned audit tooling
#: can recognise them — copying the base class into this repo instead would
#: produce two inheritance trees that cannot see each other, which is the exact
#: thing the registry exists to prevent (`EPIC-008F`).
#:
#: This is an allow-list of *exact module paths*, not a prefix: it must stay
#: impossible to widen accidentally. `sagittarius_engine.interfaces.i_event_bus`
#: is still an offender, and is meant to be — that is what `IEventPublisher`
#: and the other ports in `application/ports/` are for.
_SHARED_KERNEL_MODULES = frozenset(
    {
        "sagittarius_engine.domain.base_event",
        "sagittarius_engine.domain.i_domain_event",
    }
)


def _script_class_names() -> set[str]:
    """Every concrete BaseIndicatorScript subclass under indicator_scripts/."""
    names = set()
    for path in _SCRIPTS_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {
                base.id if isinstance(base, ast.Name) else getattr(base, "attr", None)
                for base in node.bases
            }
            if "BaseIndicatorScript" in bases:
                names.add(node.name)
    return names


def _registered_class_names() -> set[str]:
    """Class names passed to any `.register(key, Cls)` call in the module file."""
    tree = ast.parse(_MODULE_FILE.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "register"
            and len(node.args) == 2
            and isinstance(node.args[1], ast.Name)
        ):
            names.add(node.args[1].id)
    return names


def test_every_script_is_registered_in_the_module():
    """
    Registration is deliberately explicit (no directory auto-scan), so the
    failure mode it creates — writing a script and forgetting to register it,
    leaving it invisible in the UI with no error anywhere — has to be caught
    here instead.
    """
    unregistered = sorted(_script_class_names() - _registered_class_names())

    assert unregistered == [], (
        "indicator script(s) defined but never registered in "
        f"binance_bot_module.py: {unregistered}"
    )


def test_domain_layer_never_imports_a_ui_toolkit():
    """
    Scripts describe *what* to plot (name, value, hex color); turning that into
    a curve is the presentation layer's job. A QColor or a pyqtgraph import
    sneaking in here would quietly couple the domain to the desktop UI and
    break reuse from the CLI/backtest paths.

    The engine is forbidden here too, with exactly two exceptions — the Shared
    Kernel (see `_SHARED_KERNEL_MODULES`). This test is what enforces that
    boundary: anything else from `sagittarius_engine` must arrive through a
    port in `application/ports/`.
    """
    offenders = []
    for path in _DOMAIN_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                if module in _SHARED_KERNEL_MODULES:
                    continue
                if module.split(".")[0] in _FORBIDDEN_DOMAIN_IMPORTS:
                    offenders.append(f"{path.relative_to(_BOT_ROOT)} -> {module}")

    assert offenders == [], f"domain layer must stay UI-free: {offenders}"


def test_shared_kernel_allowance_does_not_open_the_whole_engine():
    """The allow-list is exact module paths, so a sibling engine module cannot
    slip through on the strength of a shared prefix. Without this, widening
    `_SHARED_KERNEL_MODULES` to a prefix later would silently re-admit the
    entire engine into the domain layer and no test would notice."""
    assert "sagittarius_engine.domain" not in _SHARED_KERNEL_MODULES
    assert "sagittarius_engine.interfaces.i_event_bus" not in _SHARED_KERNEL_MODULES
    assert all(module.count(".") >= 2 for module in _SHARED_KERNEL_MODULES)
