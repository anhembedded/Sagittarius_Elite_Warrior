"""Guard: every rule under `.claude/rules/` is listed by both navigation files.

Claude Code loads the rules by itself — every session, or when a file matching a rule's
`paths:` front matter is opened. A path-scoped rule therefore exists without announcing
itself to an agent who has not opened a matching file yet, and a planning session decides
what to touch before it opens anything. The table in `CLAUDE.md` and the reading order in
`.claude/ONBOARDING.md` are what tell that agent the rule is there.

An unlisted rule is an unread rule, and this has already cost real defects. On 2026-09-02
the `CLAUDE.md` table listed 7 of the 13 rule files; an agent read those 7, took them for
the complete set, and shipped work violating three of the six it never saw — a QML container
around the chart, a Coordinator with its own `action_id` bookkeeping, the mandatory
`preview.py` omitted. On 2026-09-16 `report-rule.md` had a row in `CLAUDE.md` and none in
the reading order, so the file an agent actually reads in order never said the rule existed.

The check is a text scan rather than a Markdown parse: the point is whether the rule's name
appears at all, which no table-formatting choice can change. A rule in a subdirectory is
looked up by its path under `rules/` (`pitfalls/tests.md`), so a row cannot satisfy this
guard with the bare word `tests.md`.

Retire when: Claude Code lists every discovered rule to the session at start — then a row
announces nothing the platform has not already said.
"""

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RULES_DIR = _REPO_ROOT / ".claude" / "rules"

#: `CLAUDE.md` is what Claude Code loads first; `ONBOARDING.md` §1 is the reading order it
#: imports. Both must name every rule.
_NAVIGATION_FILES = (
    _REPO_ROOT / "CLAUDE.md",
    _REPO_ROOT / ".claude" / "ONBOARDING.md",
)


def _rule_files() -> list[Path]:
    return sorted(_RULES_DIR.rglob("*.md"))


def _rule_id(rule: Path) -> str:
    return rule.relative_to(_RULES_DIR).as_posix()


def test_rules_directory_is_where_this_guard_expects_it() -> None:
    """Fail loudly if the rules move, rather than passing vacuously against
    an empty glob — a guard that silently checks nothing is worse than no
    guard, because it reads as coverage."""
    assert _RULES_DIR.is_dir(), f"{_RULES_DIR} is gone — this guard needs updating"
    assert len(_rule_files()) >= 10, (
        f"only {len(_rule_files())} rule files found in {_RULES_DIR}; the naming "
        "convention or the directory changed, so this guard is no longer scanning "
        "what it thinks it is"
    )


@pytest.mark.parametrize(
    "navigation_file", _NAVIGATION_FILES, ids=lambda path: path.name
)
def test_navigation_file_lists_every_rule(navigation_file: Path) -> None:
    text = navigation_file.read_text(encoding="utf-8")
    unlisted = [_rule_id(rule) for rule in _rule_files() if _rule_id(rule) not in text]

    assert not unlisted, (
        f"{navigation_file.relative_to(_REPO_ROOT)} does not mention "
        f"{len(unlisted)} rule file(s): {', '.join(unlisted)}. An agent reads "
        "this file to find out which rules exist, so a rule missing from it is "
        "a rule that does not get read — add a row pointing at each one."
    )
