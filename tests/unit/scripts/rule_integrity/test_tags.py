"""A tag's claim about its enforcement is true (`scripts/rule_integrity/tags.py`)."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.scripts.rule_integrity.tags import check_tag_grammar
from Sagittarius_Elite_Warrior.tests.unit.scripts.rule_integrity.fake_repo import (
    MakeRepo,
)

_RULE = ".claude/rules/probe-rule.md"

_FIXTURE: dict[str, str] = {
    "tests/unit/test_real.py": "",
    "tests/unit/a/test_dup.py": "",
    "tests/unit/b/test_dup.py": "",
    "pyproject.toml": '[tool.ruff.lint]\nextend-select = ["S"]\nignore = ["S105"]\n',
    "scripts/ci-local.ps1": 'Write-Step "Mypy"\n',
    ".claude/skills/pr-review/references/rubric.md": "| **A1** | a check |\n",
    ".claude/skills/test-health/contract.json": "{}\n",
}


def _messages(
    make_repo: MakeRepo, line: str, pyproject: str | None = None
) -> list[tuple[int, str]]:
    """Problems for a rule file whose third line is `line`, in the fixture repository."""
    files = {**_FIXTURE, _RULE: f"# T\n\n{line}\n"}
    if pyproject is not None:
        files["pyproject.toml"] = pyproject
    return [(p.line, p.message) for p in check_tag_grammar(make_repo(files))]


@pytest.mark.parametrize(
    "tag",
    [
        "`[guard: test_real.py]`",
        "`[guard: tests/unit/test_real.py, tests/unit/a/test_dup.py]`",
        "`[guard: <test file>]`",
        "`[gate: ruff S101]`",
        "`[gate: ruff F401]`",
        "`[gate: mypy]`",
        "`[review: A1]`",
        "`[eye]`",
        "`[contract: .claude/skills/test-health/contract.json]`",
        "`[eye; review: A1; gate: mypy]`",
        "`[chart-env]`",
        "`[chart-data]`",
    ],
)
def test_a_true_tag_is_not_reported(make_repo: MakeRepo, tag: str) -> None:
    assert _messages(make_repo, f"- Clause. {tag}") == []


@pytest.mark.parametrize(
    ("tag", "fragment"),
    [
        ("`[guard: test_missing.py]`", "names no tracked test"),
        ("`[guard: test_dup.py]`", "is ambiguous"),
        ("`[guard: that test]`", "neither a tracked path"),
        ("`[guard]`", "`guard` needs an argument"),
        ("`[gate]`", "`gate` needs an argument"),
        ("`[gate: ruff PGH004]`", "is not selected"),
        ("`[gate: ruff S105]`", "is not selected"),
        ("`[gate: run-log scan]`", "does not run it"),
        ("`[gate: lint]`", "is no step the gate runs"),
        ("`[review: Z9]`", "no Check ID"),
        ("`[review: row]`", "no Check ID"),
        ("`[eye: someone]`", "takes no argument"),
        ("`[contract: missing.json]`", "not in the repository"),
        ("`[gate, review: A1]`", "malformed tag item"),
    ],
)
def test_a_false_tag_is_reported_at_its_line(
    make_repo: MakeRepo, tag: str, fragment: str
) -> None:
    messages = _messages(make_repo, f"- Clause. {tag}")
    assert len(messages) == 1
    assert messages[0][0] == 3
    assert fragment in messages[0][1]


def test_without_a_select_ruff_defaults_apply(make_repo: MakeRepo) -> None:
    no_ruff = "[project]\nname = 'probe'\n"
    assert _messages(make_repo, "- `[gate: ruff E711]`", no_ruff) == []
    assert _messages(make_repo, "- `[gate: ruff S101]`", no_ruff) != []


def test_a_tag_in_a_fenced_block_is_not_checked(make_repo: MakeRepo) -> None:
    assert _messages(make_repo, "```\n`[review: Z9]`\n```") == []


def test_a_gate_step_may_live_in_a_workflow(make_repo: MakeRepo) -> None:
    """`EPIC-031`: a CI workflow or a Claude Code hook is a gate when it runs the step."""
    files = {
        **_FIXTURE,
        ".github/workflows/commit-lint.yml": "run: python3 scripts/check_commit_messages.py\n",
        _RULE: "# T\n\n- Clause. `[gate: commit lint]`\n- Clause. `[gate: independent review]`\n",
    }
    messages = [(p.line, p.message) for p in check_tag_grammar(make_repo(files))]
    assert len(messages) == 1
    assert messages[0][0] == 4
    assert ".github/workflows/independent-review.yml does not run it" in messages[0][1]
