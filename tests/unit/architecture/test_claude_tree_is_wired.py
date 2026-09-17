"""Guard: the `.claude/` tree is wired — every file declares itself, every scope is real,
the text loaded every session stays under its ceiling, and the manifest is the tree.

**Why this exists.** Claude Code loads `.claude/rules/*.md` by itself: a rule with a
`paths:` list in its front matter loads when a matching file is opened, a rule without one
loads every session. That is the mechanism this repository chose on 2026-09-17 when the
rules moved here from `.agents/` (`BOT-135`) — nothing has to be remembered. It leaves
exactly four ways to rot, and this guard closes each:

1. **A scope that matches nothing.** A rule whose globs name a tree that moved loads on no
   file, and nothing says so — the same shape as the pointer files this guard replaced,
   which routed to a rule by name and could rot in the same silence. Every glob must match
   at least one tracked file; `git ls-files` answers, not the disk (`CS-005`).
2. **A file that does not declare itself.** The manifest is derived from front matter, so a
   rule, skill, agent or template without a `description` is invisible there; a skill whose
   `name` differs from its directory is invoked under a name nobody typed.
3. **The always-loaded text growing quietly.** Rules without `paths:` cost every session.
   The ceiling below is a ratchet — it may fall, never rise (`ONBOARDING.md` §12.5, 8) —
   and a change that needs more lines every session scopes a rule by path instead.
4. **A manifest written by hand.** `.claude/README.md` carries the table
   `scripts/render_claude_manifest.py` prints; a hand edit disagrees with the tree by the
   next rename.

Stdlib only, on purpose: this must run wherever the rules do, without Qt or the engine.

Retire when: Claude Code itself reports an unmatched `paths:` glob or an unlisted rule —
then 1 and 4 are its job, and 2 and 3 move to `scripts/measure_process.py`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.scripts.render_claude_manifest import (
    front_matter,
    inventory,
    manifest_block,
    render_table,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLAUDE = _REPO_ROOT / ".claude"
_RULES = _CLAUDE / "rules"

#: Lines Claude Code puts in context at the start of every session: `CLAUDE.md`, the map it
#: imports, and every rule without a `paths:` list. Measured at 363 on 2026-09-17, when the
#: tree was consolidated; the ceiling leaves the map a few lines of headroom and only ever
#: moves down.
_ALWAYS_LOADED_MAX_LINES = 380

#: What `CLAUDE.md` must import for the map to be in context without being remembered.
_ONBOARDING_IMPORT = "@.claude/ONBOARDING.md"


def _rules() -> list[Path]:
    return sorted(_RULES.rglob("*.md"))


def _skills() -> list[Path]:
    return sorted((_CLAUDE / "skills").glob("*/SKILL.md"))


def _agents() -> list[Path]:
    return sorted((_CLAUDE / "agents").glob("*.md"))


def _templates() -> list[Path]:
    return sorted((_CLAUDE / "templates").glob("*.md"))


def _scoped_rules() -> dict[Path, list[str]]:
    scoped = {}
    for rule in _rules():
        paths = front_matter(rule).get("paths")
        if isinstance(paths, list):
            scoped[rule] = paths
    return scoped


def _tracked_files_matching(glob: str) -> list[str]:
    """Files the repository holds that `glob` names — git's answer, the disk's as fallback."""
    git = shutil.which("git")
    if git is not None:
        completed = subprocess.run(
            [git, "-C", str(_REPO_ROOT), "ls-files", "--", f":(glob){glob}"],
            check=True,
            capture_output=True,
            text=True,
        )
        return [line for line in completed.stdout.splitlines() if line]
    return [p.as_posix() for p in _REPO_ROOT.glob(glob) if p.is_file()]


def _relative_id(rule: Path) -> str:
    return rule.relative_to(_RULES).as_posix()


def test_the_tree_is_where_this_guard_expects_it() -> None:
    """Fail loudly rather than passing vacuously against an empty glob."""
    assert len(_rules()) >= 10, f"only {len(_rules())} rules under {_RULES}"
    assert len(_skills()) >= 3, "fewer than three skills — the layout changed"
    assert _agents(), "no subagent under .claude/agents/"
    assert _templates(), "no template under .claude/templates/"
    assert _scoped_rules(), (
        "no rule declares `paths:` — the front-matter convention changed"
    )


@pytest.mark.parametrize("rule", _rules(), ids=_relative_id)
def test_every_rule_declares_a_description(rule: Path) -> None:
    fields = front_matter(rule)
    assert fields.get("description"), (
        f"{_relative_id(rule)} has no `description:` in its front matter, so the manifest "
        "cannot say what it is. Add one line saying what the rule decides."
    )
    paths = fields.get("paths")
    assert paths is None or (isinstance(paths, list) and paths), (
        f"{_relative_id(rule)} declares `paths:` with no globs — it would load on nothing. "
        "Either list the globs or remove the key so the rule loads every session."
    )


@pytest.mark.parametrize(
    "rule, globs",
    sorted(_scoped_rules().items()),
    ids=lambda value: _relative_id(value) if isinstance(value, Path) else "",
)
def test_every_scope_glob_matches_a_tracked_file(rule: Path, globs: list[str]) -> None:
    dead = [glob for glob in globs if not _tracked_files_matching(glob)]
    assert not dead, (
        f"{_relative_id(rule)} scopes itself to {dead}, which match no file the repository "
        "holds. The rule loads on nothing and nothing says so — retarget the glob to where "
        "that code lives now, or drop it."
    )


@pytest.mark.parametrize("skill", _skills(), ids=lambda p: p.parent.name)
def test_every_skill_is_named_for_its_directory(skill: Path) -> None:
    fields = front_matter(skill)
    assert fields.get("name") == skill.parent.name, (
        f"{skill.relative_to(_CLAUDE)} declares name={fields.get('name')!r} but lives in "
        f"{skill.parent.name}/ — it is invoked as /{skill.parent.name}, so the two must agree."
    )
    assert fields.get("description"), f"{skill.relative_to(_CLAUDE)} has no description"


@pytest.mark.parametrize("path", _agents() + _templates(), ids=lambda p: p.name)
def test_every_agent_and_template_declares_a_description(path: Path) -> None:
    fields = front_matter(path)
    assert fields.get("description"), f"{path.relative_to(_CLAUDE)} has no description"
    if path.parent.name == "agents":
        assert fields.get("name") == path.stem, (
            f"{path.name}: name must equal the file stem"
        )


def test_the_text_loaded_every_session_stays_under_its_ceiling() -> None:
    claude_md = (_REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert _ONBOARDING_IMPORT in claude_md, (
        f"CLAUDE.md no longer imports {_ONBOARDING_IMPORT}; the map would have to be "
        "remembered again (ONBOARDING §12.5, principle 1)."
    )
    always = [_REPO_ROOT / "CLAUDE.md", _CLAUDE / "ONBOARDING.md"]
    always += [rule for rule in _rules() if rule not in _scoped_rules()]
    lines = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in always)
    assert lines <= _ALWAYS_LOADED_MAX_LINES, (
        f"{lines} lines load every session ({', '.join(p.name for p in always)}); the "
        f"ceiling is {_ALWAYS_LOADED_MAX_LINES}. Scope a rule with `paths:` or shorten one — "
        "the ceiling only falls."
    )


def test_the_manifest_is_the_tree() -> None:
    readme = (_CLAUDE / "README.md").read_text(encoding="utf-8")
    block = manifest_block(readme)
    assert block is not None, ".claude/README.md lost its manifest markers"
    expected = render_table(inventory(_REPO_ROOT))
    assert block == expected, (
        ".claude/README.md's inventory differs from the tree. Never edit the table by hand: "
        "run `python3 scripts/render_claude_manifest.py` and paste its output between the markers."
    )
