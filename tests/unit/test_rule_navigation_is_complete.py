"""Guard: every `.agents/rules/*.md` is listed by both navigation files.

Claude Code loads `CLAUDE.md` automatically and loads nothing else — the
`trigger: always_on` front-matter field in the rule files is a convention of
`.agents/Skills/`, not a loading mechanism. So the table in `CLAUDE.md` is
not a convenience index: it is the *only* thing that tells an agent a rule
file exists. `.agents/AGENTS.md` plays the same role for the scheduled
agents.

An unlisted rule is an unread rule, and this has already cost real defects.
On 2026-09-02 the `CLAUDE.md` table listed 7 of the 13 rule files. An agent
read those 7, took them for the complete set, and shipped work violating
three of the six it never saw — a plan that put a QML container around the
chart (`qml-rule.md` §0 forbids it: QML nests inside QtWidgets, never the
reverse), gave a Coordinator its own `action_id` bookkeeping
(`async-ui-action-rule.md` §2), and omitted the mandatory `preview.py`
(`ui-presentation-rule.md`). `AGENTS.md` listed all 13 at the same time, so
the gap was in exactly the file an interactive agent reads.

The check is a filesystem/text scan rather than a Markdown parse: the point
is whether the filename appears at all, which no table-formatting choice can
change.
"""

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RULES_DIR = _REPO_ROOT / ".agents" / "rules"

#: Both entry points, and why each one matters. `CLAUDE.md` is what Claude
#: Code itself loads; `AGENTS.md` is what the scheduled agents under
#: `.agents/Skills/` are pointed at.
_NAVIGATION_FILES = (
    _REPO_ROOT / "CLAUDE.md",
    _REPO_ROOT / ".agents" / "AGENTS.md",
)


def _rule_files() -> list[Path]:
    return sorted(_RULES_DIR.glob("*-rule.md"))


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
    unlisted = [rule.name for rule in _rule_files() if rule.name not in text]

    assert not unlisted, (
        f"{navigation_file.relative_to(_REPO_ROOT)} does not mention "
        f"{len(unlisted)} rule file(s): {', '.join(unlisted)}. An agent reads "
        "this file to find out which rules exist, so a rule missing from it is "
        "a rule that does not get read — add a row pointing at each one."
    )
