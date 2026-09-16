"""Guard: `Docs/CASE_STUDIES/` stays findable and stays true.

**Why this exists at all.** `CLAUDE.md` records an agent reading the seven rules
a table listed, taking that for the whole set, and shipping work that violated
three of the six it never saw. An unlisted document is an unread document, and
a case study is written precisely for the reader who does not yet know it
exists — so a file on disk that the index does not name has failed at the one
job the form has.

The second half is the same rot `test_spec_index_is_consistent.py` catches for
`Docs/SPEC/`: a case study is dense with repository paths — the guard it
installed, the test whose double it dissects, the rule it leans on — and
`EPIC-025` moves files by the dozen. A case study citing
`src/presentation/ui/kit/style.py` after that tree moved is a document telling a
reader to go and look at nothing.

**And the two checks specific to this form.** A case study missing
`## The fix` has not finished being written: the premise of the directory is
that the next instance fails a machine rather than a reader's attention. Same
for `## Where else this is still open`, the section that makes the document
worth more than its bug report. And it must stay a **short list** rather than
an analysis (user decision 2026-09-16): the first draft of `CS-001` ran to 150
lines by restating its bug report, which is the one thing this directory must
not do.

Stdlib only, like the other document guards here: it must run without Qt or the
engine installed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DIR = _REPO_ROOT / "Docs" / "CASE_STUDIES"
_INDEX = _DIR / "README.md"

#: `CS-001_slug.md`. The id carries no meaning beyond order; the slug is what a
#: reader recognises in a commit message.
_FILENAME = re.compile(r"^CS-(\d{3})_[a-z0-9_]+\.md$")

#: A markdown link to a sibling case study from inside the index's table.
_INDEXED = re.compile(r"\[CS-(\d{3})\]\((CS-\d{3}_[a-z0-9_]+\.md)\)")

#: Sections every case study must carry. Each one is the answer to a question
#: the form exists to force; a file without it is a bug report in a different
#: directory.
_REQUIRED_SECTIONS = (
    "## Why nothing caught it",
    "## The fix",
    "## Where else this is still open",
)

#: A repository path mentioned inside a backtick. Deliberately narrow: it must
#: look like a path (contain a `/`) and start at a top-level directory this
#: repository actually has, so prose like `IEventBus.emit` is not mistaken for
#: a file. Trailing punctuation and a `:line` suffix are trimmed by the caller.
_CITED_PATH = re.compile(
    r"`((?:src|tests|scripts|tools|Docs|Tasks|\.agents|\.claude)/[A-Za-z0-9_./*-]+)`"
)

#: A markdown link to a file, `[text](path)`. The other half of the citation
#: check: a case study links its bug report and its rules that way, and a
#: relative link is exactly what a moved file breaks. `http(s)` and pure
#: anchors are skipped.
_CITED_LINK = re.compile(r"\]\((?!https?:|#)([^)\s]+)\)")

#: Lines. A case study is a **short list**, not an analysis (user decision
#: 2026-09-16) — a table of nets and three bullet groups. A length nobody
#: checks is a length that drifts back into prose: the first draft of `CS-001`
#: ran to 150 lines by restating its own bug report, which is the one thing
#: this directory must not do. 35 is what the first entry needed, with the
#: table and three bullet groups the form requires and nothing else.
_MAX_LINES = 35


def _case_study_files() -> list[Path]:
    return sorted(p for p in _DIR.glob("*.md") if p.name != "README.md")


def test_the_directory_and_its_index_exist() -> None:
    """The non-emptiness assertion `HLD` §9.3 rule 4 asks of every
    path-scanning guard: this one's scan going empty would make every test
    below pass while checking nothing."""
    assert _DIR.is_dir(), f"no case-study directory at {_DIR}"
    assert _INDEX.is_file(), f"no index at {_INDEX}"
    assert _case_study_files(), (
        "the case-study directory holds no case study. If the practice was "
        "dropped, delete the directory, its index and this guard together — "
        "leaving an empty directory behind makes a guard that watches nothing."
    )


def test_every_filename_follows_the_convention() -> None:
    bad = [p.name for p in _case_study_files() if not _FILENAME.match(p.name)]

    assert bad == [], f"a case study must be named `CS-NNN_lower_snake_slug.md`: {bad}"


def test_every_case_study_on_disk_is_listed_in_the_index() -> None:
    """The `CLAUDE.md` failure, made mechanical: an unlisted document is an
    unread one, and this form is written for a reader who does not know it is
    there."""
    listed = {name for _, name in _INDEXED.findall(_INDEX.read_text(encoding="utf-8"))}
    on_disk = {p.name for p in _case_study_files()}

    assert on_disk - listed == set(), (
        f"case study on disk but missing from {_INDEX.name}: {sorted(on_disk - listed)}"
    )


def test_the_index_lists_nothing_that_is_missing() -> None:
    listed = {name for _, name in _INDEXED.findall(_INDEX.read_text(encoding="utf-8"))}
    on_disk = {p.name for p in _case_study_files()}

    assert listed - on_disk == set(), (
        f"{_INDEX.name} links a case study that does not exist: "
        f"{sorted(listed - on_disk)}"
    )


def test_ids_are_unique() -> None:
    ids = [_FILENAME.match(p.name).group(1) for p in _case_study_files()]

    assert len(ids) == len(set(ids)), (
        f"two case studies share an id: {sorted(ids)}. Ids are sequential and "
        "never reused — a reader citing `CS-00x` must reach one document."
    )


@pytest.mark.parametrize("path", _case_study_files(), ids=lambda p: p.name)
def test_every_case_study_carries_the_sections_that_make_it_one(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [section for section in _REQUIRED_SECTIONS if section not in text]

    assert missing == [], (
        f"{path.name} is missing {missing}. Without them it is a bug report "
        "filed in the wrong directory: the sections are what force the two "
        "questions this form exists for — which safety net was silent and "
        "why, and where the same blind spot is still open."
    )


@pytest.mark.parametrize("path", _case_study_files(), ids=lambda p: p.name)
def test_every_repository_path_a_case_study_cites_still_resolves(path: Path) -> None:
    """A case study is dense with paths, and `EPIC-025` moves files by the
    dozen. A citation that no longer resolves sends a reader to look at
    nothing — the same rot `scripts/check_skill_prompt_references.py` catches
    for the prompt trees, and it found a real one on its first run."""
    text = path.read_text(encoding="utf-8")
    broken = []
    for raw in _CITED_PATH.findall(text):
        candidate = raw.rstrip(".,:;")
        candidate = candidate.split(":")[0]
        if "*" in candidate:
            continue  # a glob describing a family, not one file
        if not (_REPO_ROOT / candidate).exists():
            broken.append(candidate)

    assert broken == [], (
        f"{path.name} cites repository paths that no longer exist: "
        f"{sorted(set(broken))}. Retarget them, or say in the text that the "
        "file was deleted and when — a case study describing a tree that has "
        "moved is worth less than one that says where it went."
    )


@pytest.mark.parametrize("path", _case_study_files(), ids=lambda p: p.name)
def test_every_case_study_stays_one_screen(path: Path) -> None:
    """Short is the form, not a preference. The first draft of `CS-001` ran to
    150 lines and said nothing the 40-line version does not — the length was
    restating the bug report, which is the one thing this directory must not
    do."""
    lines = len(path.read_text(encoding="utf-8").splitlines())

    assert lines <= _MAX_LINES, (
        f"{path.name} is {lines} lines, over the {_MAX_LINES}-line cap. Cut the "
        "narration, keep the table: a case study that restates its bug report "
        "has stopped being one."
    )


@pytest.mark.parametrize("path", _case_study_files(), ids=lambda p: p.name)
def test_every_markdown_link_a_case_study_makes_resolves(path: Path) -> None:
    """The other half of the citation check. A case study links its bug report
    and the rules it leans on, and those links are relative — so a moved or
    renamed file turns them into a reader sent nowhere."""
    text = path.read_text(encoding="utf-8")
    broken = [
        target
        for target in _CITED_LINK.findall(text)
        if not (path.parent / target.split("#")[0]).resolve().exists()
    ]

    assert broken == [], (
        f"{path.name} links targets that do not resolve: {sorted(set(broken))}"
    )
