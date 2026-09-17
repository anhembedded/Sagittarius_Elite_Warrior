"""
No new `.qml` file may appear anywhere under `src/` (ADR D20, HLD §11).

**It is a ban now, and was a ratchet until `EPIC-025` PR 4.3l.** The 35 files
this started with had to stay alive while the strangler migration ran, so the
rule was "no file outside `baseline_qml_files.txt`, and the list only shrinks".
PR 4.3l deleted the last of them: the baseline is **empty**, which turns the
same two assertions into "no `.qml` under `src/`, anywhere".

**How.** `baseline_qml_files.txt` next to this file lists the `.qml` paths still
tolerated — none. The test fails when a file on disk is missing from the list (a
new QML file) and when a listed file no longer exists (a deletion landed —
remove the line in the same commit).

`test_scanned_roots_are_not_empty.py` would normally fail a guard whose scan
matches nothing, because that is what a guard looks like after its tree moved
under it. This one is registered in that registry's `EMPTY_BY_DESIGN`: an empty
scan here is the ADR being satisfied, and the exemption names this exact
(guard, root, pattern) so a second, genuinely-emptied root would still fail.
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
