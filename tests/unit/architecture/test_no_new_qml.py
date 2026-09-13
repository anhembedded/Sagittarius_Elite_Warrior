"""
No new `.qml` file may appear anywhere under `src/` (ADR D20, HLD §11).

**Why.** `EPIC-025` rebuilds every screen as QtWidgets and the QML runtime is
retired with the last screen. A ratchet — not a ban — because the 35 files
below stay alive while the strangler migration runs; each phase deletes some.

**How.** `baseline_qml_files.txt` next to this file lists every `.qml` path as
found in Phase 0. The test fails when a file on disk is missing from the list
(a new QML file) **and** when a listed file no longer exists (the deletion
landed — remove the line in the same commit). The list only shrinks; it is
empty when Phase 4 closes and this guard is retired together with `qml-rule.md`.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
_BASELINE_FILE = Path(__file__).with_name("baseline_qml_files.txt")


def _qml_files_on_disk() -> set[str]:
    return {p.relative_to(_REPO_ROOT).as_posix() for p in _SRC_ROOT.rglob("*.qml")}


def _baseline() -> list[str]:
    return [
        line.strip()
        for line in _BASELINE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_src_root_is_where_we_think_it_is() -> None:
    assert (_SRC_ROOT / "presentation").is_dir(), f"no src tree at {_SRC_ROOT}"


def test_no_qml_file_outside_the_baseline() -> None:
    new_files = sorted(_qml_files_on_disk() - set(_baseline()))
    assert new_files == [], (
        "a .qml file was added. EPIC-025 builds UI as QtWidgets only (ADR D20);\n"
        "the baseline never grows.\n  " + "\n  ".join(new_files)
    )


def test_the_baseline_has_not_gone_stale() -> None:
    gone = sorted(set(_baseline()) - _qml_files_on_disk())
    assert gone == [], (
        "baseline lists .qml files that no longer exist — delete these lines:\n  "
        + "\n  ".join(gone)
    )


def test_the_baseline_has_no_duplicates() -> None:
    entries = _baseline()
    assert len(entries) == len(set(entries))
