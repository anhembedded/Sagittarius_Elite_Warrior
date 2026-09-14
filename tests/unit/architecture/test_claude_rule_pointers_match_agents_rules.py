"""Guard: `.claude/rules/` routes to `.agents/rules/` and never diverges from it.

**Why this exists.** The rule files under `.agents/rules/` have always declared
their own scope — `trigger: on_file_change` plus a `patterns:` list — but
`CLAUDE.md` records that nothing executed it: the field was a convention of
`.agents/Skills/`, not a loading mechanism. Claude Code does load `.claude/rules/*.md`,
and a `paths:` list there scopes a file to the sources it belongs to. So each
`on_file_change` rule gets a thin pointer under `.claude/rules/` carrying the same
globs, and the rule text stays in one place.

That leaves exactly two ways for this to rot, and this guard closes both:

1. **A copy that drifts.** The repository has caught the drifted-copy disease twice
   (`CLAUDE.md`: `AGENTS.md` was once a near-verbatim copy of `code-rule.md` and
   carried a wrong `Co-Authored-By` trailer). A pointer is allowed to route; it is
   not allowed to grow into a second copy of the rule, so its size is capped.
2. **A new rule with no pointer.** Adding an `on_file_change` rule and forgetting
   its pointer fails silently — the rule simply never loads, and nothing says so.
   That is the same shape as an allowlist with no completeness check.

Stdlib only, on purpose: this must run wherever the rules do, without Qt or the
engine installed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_AGENTS_RULES = _REPO_ROOT / ".agents" / "rules"
_CLAUDE_RULES = _REPO_ROOT / ".claude" / "rules"

#: A pointer routes; it never restates. Generous enough for a real explanation,
#: far below the size of any rule file it could be tempted to absorb.
_POINTER_MAX_LINES = 30

_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_TRIGGER_RE = re.compile(r"^trigger:\s*(\S+)\s*$", re.MULTILINE)


def _front_matter(path: Path) -> str:
    match = _FRONT_MATTER_RE.match(path.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def _glob_list(front_matter: str, key: str) -> list[str]:
    """Return the values of a `key:` block written as a YAML list of strings."""
    globs: list[str] = []
    collecting = False
    for line in front_matter.splitlines():
        if re.match(rf"^{key}:\s*$", line):
            collecting = True
            continue
        if collecting:
            item = re.match(r"^\s+-\s*(.+?)\s*$", line)
            if item is None:
                break
            globs.append(item.group(1).strip().strip("\"'"))
    return globs


def _path_scoped_rules() -> dict[Path, list[str]]:
    """Every `.agents/rules/` file that declares itself scoped to given sources."""
    scoped = {}
    for rule in sorted(_AGENTS_RULES.glob("*-rule.md")):
        front_matter = _front_matter(rule)
        trigger = _TRIGGER_RE.search(front_matter)
        if trigger is not None and trigger.group(1) == "on_file_change":
            scoped[rule] = _glob_list(front_matter, "patterns")
    return scoped


def _pointers() -> list[Path]:
    return sorted(_CLAUDE_RULES.glob("*.md"))


def _pointer_for(rule: Path) -> Path:
    """`.agents/rules/foo-rule.md` is routed by `.claude/rules/foo.md`.

    The mapping is by filename, deliberately. Searching the pointer's prose for
    the rule's name looks friendlier and is wrong: a pointer may legitimately
    mention a neighbouring rule, which made this guard report two pointers for
    one rule the first time it ran.
    """
    return _CLAUDE_RULES / f"{rule.name.removesuffix('-rule.md')}.md"


def _rule_for(pointer: Path) -> Path:
    return _AGENTS_RULES / f"{pointer.stem}-rule.md"


def test_both_rule_directories_are_where_this_guard_expects_them() -> None:
    """Fail loudly rather than passing vacuously against an empty glob."""
    assert _AGENTS_RULES.is_dir(), f"{_AGENTS_RULES} is gone — retarget this guard"
    assert _CLAUDE_RULES.is_dir(), f"{_CLAUDE_RULES} is gone — retarget this guard"
    assert _pointers(), f"no pointer files found in {_CLAUDE_RULES}"
    assert _path_scoped_rules(), (
        "no rule declares `trigger: on_file_change`; the front-matter convention "
        "changed, so this guard is no longer checking what it thinks it is"
    )


@pytest.mark.parametrize(
    "rule", sorted(_path_scoped_rules()), ids=lambda path: path.name
)
def test_every_path_scoped_rule_has_a_pointer(rule: Path) -> None:
    pointer = _pointer_for(rule)
    assert pointer.is_file(), (
        f"{rule.name} declares `trigger: on_file_change`, so it is meant to load "
        f"when Claude reads a matching file — but {pointer.relative_to(_REPO_ROOT)} "
        f"does not exist, so nothing loads it and nothing says so. Add a thin "
        f"pointer there carrying the same globs."
    )
    assert rule.name in pointer.read_text(encoding="utf-8"), (
        f"{pointer.name} is named for {rule.name} but never links to it — a pointer "
        f"that does not name its rule routes nowhere."
    )


@pytest.mark.parametrize("pointer", _pointers(), ids=lambda path: path.name)
def test_every_pointer_routes_to_a_rule_that_exists(pointer: Path) -> None:
    rule = _rule_for(pointer)
    assert rule.is_file(), (
        f"{pointer.name} routes to {rule.name}, which does not exist. A pointer "
        f"left behind by a deleted or renamed rule loads on every matching file "
        f"and sends the reader to nothing."
    )


@pytest.mark.parametrize(
    "rule", sorted(_path_scoped_rules()), ids=lambda path: path.name
)
def test_pointer_globs_match_the_rule_they_route_to(rule: Path) -> None:
    pointer = _pointer_for(rule)
    if not pointer.is_file():
        pytest.skip("covered by test_every_path_scoped_rule_has_a_pointer")

    declared = _path_scoped_rules()[rule]
    routed = _glob_list(_front_matter(pointer), "paths")
    assert routed == declared, (
        f"{pointer.name} routes {routed} but {rule.name} declares {declared}. "
        "The two must stay identical: the pointer decides when the rule actually "
        "loads, so a divergence silently scopes the rule to the wrong files."
    )


@pytest.mark.parametrize("pointer", sorted(_pointers()), ids=lambda path: path.name)
def test_pointer_stays_a_pointer(pointer: Path) -> None:
    lines = len(pointer.read_text(encoding="utf-8").splitlines())
    assert lines <= _POINTER_MAX_LINES, (
        f"{pointer.name} is {lines} lines. A pointer routes to a rule; it does not "
        "restate one. Rule text belongs in .agents/rules/ and nowhere else — a "
        "second copy drifts, which this repository has already paid for twice."
    )
