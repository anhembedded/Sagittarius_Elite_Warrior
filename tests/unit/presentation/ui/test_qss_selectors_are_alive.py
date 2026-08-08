"""
Guards against dead QSS rules accumulating as screens migrate to QML.

Every `#foo` selector in style.qss can only ever match a widget whose
objectName was set to "foo" somewhere in src/. When a screen moves to QML
its widgets disappear, and any rule that targeted them silently becomes
cruft — exactly what happened to the `#sidebar_*` rules when the sidebar
became QML in BOT-030 Phase 1 (found only by manually diffing the two
lists). This test makes that failure automatic instead of relying on
someone remembering.

Pure static analysis (regex over text + ast over Python) — no PySide6
import, no qapp fixture needed.
"""

import ast
import re
from pathlib import Path

_UI_ROOT = Path(__file__).resolve().parents[4] / "src" / "presentation" / "ui"
_QSS_PATH = _UI_ROOT / "qss" / "style.qss"

# `#name` at the start of a selector, e.g. "#base_card {" or
# "#base_card_header, #other {". Deliberately ignores Qt's own
# `QWidget#name` form — none is used today, and matching it would need a
# real CSS parser rather than this cheap guard.
_ID_SELECTOR_PATTERN = re.compile(r"#([A-Za-z_][A-Za-z0-9_]*)")

_COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)


def _qss_id_selectors() -> set[str]:
    source = _COMMENT_PATTERN.sub("", _QSS_PATH.read_text(encoding="utf-8"))
    # Only look at selector text (before each rule's "{"), so hex colors
    # like "#F3BA2F" inside declaration blocks are never mistaken for ids.
    selectors = set()
    for block in source.split("}"):
        selector_text = block.split("{")[0]
        selectors.update(_ID_SELECTOR_PATTERN.findall(selector_text))
    return selectors


def _object_names_set_in_source() -> set[str]:
    """Collects every string literal passed to setObjectName(...) in src/."""
    names: set[str] = set()
    for path in _UI_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if getattr(func, "attr", None) != "setObjectName":
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    names.add(arg.value)
    return names


def test_every_qss_id_selector_matches_a_real_object_name():
    orphans = sorted(_qss_id_selectors() - _object_names_set_in_source())

    assert orphans == [], (
        "style.qss has rules for objectNames nothing sets anymore — delete "
        f"them (likely left behind by a screen moving to QML): {orphans}"
    )
