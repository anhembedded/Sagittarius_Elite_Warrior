"""`§` citations and `Pn` references resolve (`citations.py`, `invariants.py`)."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.scripts.rule_integrity.citations import (
    check_citations,
    count_skipped,
)
from Sagittarius_Elite_Warrior.scripts.rule_integrity.invariants import (
    check_invariant_refs,
)
from Sagittarius_Elite_Warrior.tests.unit.scripts.rule_integrity.fake_repo import (
    MakeRepo,
)

_SOURCE = ".claude/rules/source-rule.md"

_DOCUMENTS: dict[str, str] = {
    ".claude/rules/ci-rule.md": (
        "# CI\n\n## 1. Cadence\ntext\n\n## 1b. Python\ntext\n\n"
        "## 2. Levels\n### 2.1 Unit\ntext\n\n## 3. Failures\n1. first\n2. second\n"
    ),
    ".claude/rules/code/plain.md": "# Plain\n\n1. one\n2. two\n",
    ".claude/ONBOARDING.md": "# Map\n\n## 7. Authority\ntext\n",
    ".claude/CONSTITUTION.md": "# C\n\n## The Invariants\n"
    + "".join(f"{n}. **Invariant {n}.** text\n" for n in range(1, 12)),
}


def _citation_problems(make_repo: MakeRepo, body: str) -> list[tuple[int, str]]:
    source = f"# Source\n\n## 1. Own section\n{body}\n"
    repository = make_repo({**_DOCUMENTS, _SOURCE: source})
    return [
        (p.line, p.message) for p in check_citations(repository) if p.source == _SOURCE
    ]


@pytest.mark.parametrize(
    "line",
    [
        "See `ci-rule.md` §1b, §2.1 and §3.2.",
        "See `.claude/rules/ci-rule.md` §1–§3.",
        "See [the CI rule](ci-rule.md) §2.",
        "See `code/plain.md` §2 and plain.md §1.",
        "ONBOARDING §7 and `ONBOARDING.md` §7 decide.",
        "A bare §1 binds to this file.",
        "HLD §9.3 is not modelled.",
    ],
)
def test_a_resolving_citation_is_not_reported(make_repo: MakeRepo, line: str) -> None:
    assert _citation_problems(make_repo, line) == []


@pytest.mark.parametrize(
    ("line", "fragment"),
    [
        ("See `ci-rule.md` §9.", "has no §9"),
        ("See `ci-rule.md` §1–§9.", "has no §9"),
        ("See [the CI rule](ci-rule.md) §4.", "has no §4"),
        ("ONBOARDING §12.5 says so.", "has no §12.5"),
        ("A bare §5 binds to this file.", "source-rule.md` has no §5"),
        ("See `nowhere.md` §1.", "names no document"),
        ("See §ci-rule.md for the rule.", "not followed by a section number"),
    ],
)
def test_a_broken_citation_is_reported_at_its_line(
    make_repo: MakeRepo, line: str, fragment: str
) -> None:
    problems = _citation_problems(make_repo, line)
    assert [number for number, _ in problems] == [4]
    assert fragment in problems[0][1]


def test_a_citation_in_a_fence_is_not_checked(make_repo: MakeRepo) -> None:
    assert _citation_problems(make_repo, "```\n`ci-rule.md` §9\n```") == []


def test_a_workflow_citation_is_checked(make_repo: MakeRepo) -> None:
    repository = make_repo(
        {
            **_DOCUMENTS,
            ".github/workflows/ci.yml": "# green (ci-rule.md §8)\non: push\n",
        }
    )
    problems = check_citations(repository)
    assert [(p.source, p.line) for p in problems] == [(".github/workflows/ci.yml", 1)]


def test_unmodelled_citations_are_counted(make_repo: MakeRepo) -> None:
    repository = make_repo(
        {**_DOCUMENTS, _SOURCE: "# S\n\nHLD §9.3, SDD §4 and ADR §5.\n"}
    )
    assert count_skipped(repository) == 3


def _ref_problems(make_repo: MakeRepo, line: str) -> list[str]:
    repository = make_repo({**_DOCUMENTS, _SOURCE: f"# Source\n\n{line}\n"})
    return [p.message for p in check_invariant_refs(repository)]


@pytest.mark.parametrize(
    "line",
    [
        "All invariants (P1–P11) hold; P6 and `P6` too.",
        "Paths like `docs/P12/x.md` and Docs/P12 are not refs.",
    ],
)
def test_an_existing_invariant_is_not_reported(make_repo: MakeRepo, line: str) -> None:
    assert _ref_problems(make_repo, line) == []


@pytest.mark.parametrize(
    ("line", "fragment"),
    [
        ("See P12.", "P12 does not exist"),
        ("All invariants (P1–P10) hold.", "P1–P10 is not every invariant"),
    ],
)
def test_a_missing_or_short_invariant_ref_is_reported(
    make_repo: MakeRepo, line: str, fragment: str
) -> None:
    problems = _ref_problems(make_repo, line)
    assert len(problems) == 1
    assert fragment in problems[0]


def test_a_constitution_whose_invariants_cannot_be_found_is_reported(
    make_repo: MakeRepo,
) -> None:
    """A renamed heading must not switch the Pn checks off silently."""
    documents = {
        **_DOCUMENTS,
        ".claude/CONSTITUTION.md": "# C\n\n## The Core Invariants\n1. **One.** text\n",
        _SOURCE: "# Source\n\nCite P99 here.\n",
    }
    problems = check_invariant_refs(make_repo(documents))
    assert [p.source for p in problems] == [".claude/CONSTITUTION.md"]
    assert "no numbered invariants" in problems[0].message
