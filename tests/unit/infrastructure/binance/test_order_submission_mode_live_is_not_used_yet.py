"""`EPIC-021F` — nothing in `src/`/`scripts/` may reference
`OrderSubmissionMode.LIVE` as a real expression until `EPIC-021G` opens
live order submission. `git mv`/edit this guard when that task lifts it.

@details Scans by `ast` for an `Attribute` node (`OrderSubmissionMode.LIVE`
used as a value — a constructor argument, a dict key, a comparison, ...),
not plain text: a docstring or comment *explaining* this rule necessarily
has to spell out the name it forbids, and flagging that would make the
rule impossible to document. Mirrors
`test_only_the_session_factory_constructs_binance_client.py`'s shape
(`EPIC-021A`).
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCANNED_DIRS = (_REPO_ROOT / "src", _REPO_ROOT / "scripts")


def _references_live_mode(source: str, filename: str) -> bool:
    tree = ast.parse(source, filename=filename)
    return any(
        isinstance(node, ast.Attribute)
        and node.attr == "LIVE"
        and isinstance(node.value, ast.Name)
        and node.value.id == "OrderSubmissionMode"
        for node in ast.walk(tree)
    )


def _files_referencing_live_mode() -> list[Path]:
    hits: list[Path] = []
    for scanned_dir in _SCANNED_DIRS:
        for path in sorted(scanned_dir.rglob("*.py")):
            if _references_live_mode(path.read_text(encoding="utf-8"), str(path)):
                hits.append(path)
    return hits


def test_no_call_site_uses_live_submission_mode_yet() -> None:
    hits = _files_referencing_live_mode()
    assert hits == [], (
        f"OrderSubmissionMode.LIVE referenced outside EPIC-021G: "
        f"{[str(p.relative_to(_REPO_ROOT)) for p in hits]}"
    )


def test_guard_actually_detects_a_violation() -> None:
    """Mutation-verify (`testing-rule.md` §2): prove the scanner fires on a
    real usage shape, and correctly ignores a docstring merely naming it."""
    assert _references_live_mode(
        "from x import OrderSubmissionMode\n\nmode = OrderSubmissionMode.LIVE\n",
        "<violation-fixture>",
    )
    assert not _references_live_mode(
        '"""Do not use OrderSubmissionMode.LIVE here."""\n',
        "<docstring-only-fixture>",
    )
