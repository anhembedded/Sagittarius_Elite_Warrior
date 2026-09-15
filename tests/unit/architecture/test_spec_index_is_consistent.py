"""Guard: `Docs/SPEC/` stays a specification instead of decaying into prose.

**Why this exists.** `Docs/SPEC/` holds one use case per file, and the section
that gives it its value is the last one: *Proven by*, where every promise names
the test that holds it or the words **the user runs it**. A behaviour document
whose evidence column is not checked rots in exactly two ways, and both have
already happened elsewhere in this repository:

1. **A cited test that no longer exists.** `EPIC-025` moves test files by the
   dozen — PR 1.3a moved 24 in one commit — and a renamed path leaves the
   document claiming proof it cannot produce. This is the same failure
   `scripts/check_skill_prompt_references.py` catches for the prompt trees, and
   it caught a real one on its first run.
2. **A file nobody can find.** `CLAUDE.md` records an agent reading the seven
   rules a table listed, taking that for the whole set, and violating three of
   the six it never saw. An unlisted document is an unread one, so a `SPEC` on
   disk must appear in the index, and an id the index only *reserves* must not
   already be on disk under a different title.

The structural checks are the cheap half: a file missing *What this use case
does NOT promise* is missing the section that keeps the app from being read as
more capable than it is (`domain-truth-rule.md`), and nothing else would say so.

Stdlib only, like the other document guards here: it must run without Qt or the
engine installed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SPEC_DIR = _REPO_ROOT / "Docs" / "SPEC"
_INDEX = _SPEC_DIR / "README.md"

#: `SPEC-000_template.md` is the shape every other file copies. It is indexed
#: by the README's prose rather than its table, and its own tables are
#: deliberately empty headers, so the row-level checks below skip it.
_TEMPLATE_ID = "SPEC-000"

_SPEC_FILE_RE = re.compile(r"^SPEC-(\d{3})_[a-z0-9]+(?:_[a-z0-9]+)*\.md$")

#: The eight sections of `SPEC-000_template.md`, in order. Copied here as the
#: expected list rather than read back from the template, because a guard that
#: reads its own expectation out of the file under test cannot fail.
_REQUIRED_SECTIONS: tuple[str, ...] = (
    "1. Trigger",
    "2. Preconditions",
    "3. Main flow",
    "4. What must be true afterwards",
    "5. When it goes wrong",
    "6. What this use case does NOT promise",
    "7. Ports and modules it exercises",
    "8. Proven by",
)

#: The four bullets every SPEC opens with.
_REQUIRED_FIELDS: tuple[str, ...] = ("Status:", "Actor:", "Origin:", "Surfaces:")

#: The three honest answers, and no others: built and proven, partly built,
#: specified but not built.
_STATUS_MARKS: tuple[str, ...] = ("✅", "🟡", "🔵")

#: A linked index row: `| [SPEC-001](SPEC-001_….md) | … |`.
_INDEXED_RE = re.compile(r"\[\s*(SPEC-\d{3})\s*\]\(([^)]+\.md)\)")
#: A reserved row names the id as plain text, with no link and no file yet.
_RESERVED_RE = re.compile(r"^\|\s*(SPEC-\d{3})\s*\|", re.MULTILINE)

_TEST_PATH_RE = re.compile(r"`(tests/[^`]+?\.py)`")


def _spec_files() -> list[Path]:
    return sorted(p for p in _SPEC_DIR.glob("SPEC-*.md") if _SPEC_FILE_RE.match(p.name))


def _spec_id(path: Path) -> str:
    return path.name.split("_", 1)[0]


def _sections(text: str) -> list[str]:
    return [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]


def _index_text() -> str:
    return _INDEX.read_text(encoding="utf-8")


def test_the_spec_directory_is_not_empty() -> None:
    """HLD §9.3 rule 4: a scan that finds nothing must fail, not pass quietly."""
    assert _INDEX.is_file(), f"{_INDEX} is missing — the index is how a SPEC is found"
    assert (_SPEC_DIR / f"{_TEMPLATE_ID}_template.md").is_file(), (
        "SPEC-000_template.md is the shape every file copies; it may not be deleted"
    )
    assert _spec_files(), f"no SPEC files matched under {_SPEC_DIR}"


def test_every_spec_filename_follows_the_convention() -> None:
    """`SPEC-<three digits>_<snake_case slug>.md`, so an id sorts and never
    collides with a differently-spelled copy of itself."""
    strays = [
        p.name
        for p in _SPEC_DIR.glob("SPEC-*.md")
        if _SPEC_FILE_RE.match(p.name) is None
    ]
    assert not strays, f"filenames do not follow SPEC-<ddd>_<slug>.md: {strays}"


def test_spec_ids_are_unique() -> None:
    """Ids are permanent and never reused; two files claiming one id means one
    of them is about to be cited wrongly."""
    seen: dict[str, str] = {}
    clashes: list[str] = []
    for path in _spec_files():
        spec_id = _spec_id(path)
        if spec_id in seen:
            clashes.append(f"{spec_id}: {seen[spec_id]} and {path.name}")
        seen[spec_id] = path.name
    assert not clashes, f"duplicate SPEC ids: {clashes}"


@pytest.mark.parametrize("path", _spec_files(), ids=lambda p: p.name)
def test_every_spec_has_the_template_sections_in_order(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert _sections(text) == list(_REQUIRED_SECTIONS), (
        f"{path.name} does not carry SPEC-000_template.md's eight sections in "
        f"order — found {_sections(text)}"
    )


@pytest.mark.parametrize("path", _spec_files(), ids=lambda p: p.name)
def test_every_spec_declares_status_actor_origin_and_surfaces(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    header = text.split("## 1. Trigger", 1)[0]
    missing = [field for field in _REQUIRED_FIELDS if f"**{field}" not in header]
    assert not missing, f"{path.name} is missing its opening {missing}"
    if _spec_id(path) != _TEMPLATE_ID:
        assert any(mark in header for mark in _STATUS_MARKS), (
            f"{path.name}'s status is not one of {_STATUS_MARKS} — a SPEC says "
            "whether it is built, partly built or only specified"
        )


@pytest.mark.parametrize("path", _spec_files(), ids=lambda p: p.name)
def test_every_cited_test_path_exists(path: Path) -> None:
    """The point of *Proven by*. A moved test file renames the proof, and a
    document still claiming the old path is a document claiming evidence it
    cannot produce."""
    dangling = [
        cited
        for cited in _TEST_PATH_RE.findall(path.read_text(encoding="utf-8"))
        if not (_REPO_ROOT / cited).exists()
    ]
    assert not dangling, (
        f"{path.name} cites test paths that do not exist: {dangling} — either the "
        "file moved (update the citation) or the proof was never written"
    )


@pytest.mark.parametrize(
    "path",
    [p for p in _spec_files() if _spec_id(p) != _TEMPLATE_ID],
    ids=lambda p: p.name,
)
def test_every_spec_proves_something(path: Path) -> None:
    """A *Proven by* table with only its header is a plan, not a spec — and a
    ✅ one is a false claim, which is the failure this whole directory exists to
    prevent."""
    proven_by = path.read_text(encoding="utf-8").split("## 8. Proven by", 1)[1]
    rows = [
        line
        for line in proven_by.splitlines()
        if line.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", line)
    ]
    # Two of those rows are the table's own header and nothing else.
    assert len(rows) > 1, (
        f"{path.name}'s 'Proven by' table has no rows: name the test that holds "
        "each promise, or the words 'the user runs it' with what a person must see"
    )


@pytest.mark.parametrize(
    "path",
    [p for p in _spec_files() if _spec_id(p) != _TEMPLATE_ID],
    ids=lambda p: p.name,
)
def test_every_spec_on_disk_is_linked_from_the_index(path: Path) -> None:
    """An unlisted document is an unread one (`CLAUDE.md`)."""
    linked = dict(_INDEXED_RE.findall(_index_text()))
    spec_id = _spec_id(path)
    assert spec_id in linked, (
        f"{spec_id} exists as {path.name} but the index in Docs/SPEC/README.md "
        "does not link it"
    )
    assert linked[spec_id] == path.name, (
        f"the index links {spec_id} as {linked[spec_id]}, but the file is {path.name}"
    )


def test_the_index_links_nothing_that_is_missing() -> None:
    dangling = [
        f"{spec_id} -> {target}"
        for spec_id, target in _INDEXED_RE.findall(_index_text())
        if not (_SPEC_DIR / target).is_file()
    ]
    assert not dangling, f"the index links SPEC files that do not exist: {dangling}"


def test_a_reserved_id_is_not_already_written() -> None:
    """The second table reserves ids so two people do not invent the same
    number. Once the file exists, its row moves into the linked index — leaving
    it reserved hides a written spec from every reader of the index."""
    index = _index_text()
    linked = set(dict(_INDEXED_RE.findall(index)))
    on_disk = {_spec_id(p) for p in _spec_files()} - {_TEMPLATE_ID}
    reserved = set(_RESERVED_RE.findall(index)) - linked
    written_but_reserved = sorted(reserved & on_disk)
    assert not written_but_reserved, (
        f"{written_but_reserved} exist on disk but are still listed as reserved "
        "in Docs/SPEC/README.md — move the row into the index above"
    )
