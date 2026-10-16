"""`EPIC-041J` — a pull request that changes a documented module answers for its design.

Probes: each test goes red when the check is weakened in the way its name says
(a module folder no longer counted, the waiver accepted without a reason or
outside `## Design`, the diff read two-dot, the workflow step removed).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.scripts import check_design_in_step
from Sagittarius_Elite_Warrior.scripts.check_design_in_step import (
    changed_paths,
    documented_modules,
    problems,
)

_ROOT = Path(__file__).resolve().parents[3]
_CODE = "src/modules/alerting/application/alert_hub.py"
_DESIGN = "Docs/MODULES/alerting/05-building-blocks.md"
_DOCUMENTED = frozenset({"alerting"})
_WAIVER = "## Design\n\nNo design change: a log message only.\n"


def test_code_without_design_or_waiver_fails() -> None:
    found = problems([_CODE], "", _DOCUMENTED)
    assert len(found) == 1 and "src/modules/alerting/" in found[0]


def test_code_with_its_design_folder_passes() -> None:
    assert problems([_CODE, _DESIGN], "", _DOCUMENTED) == []


def test_the_waiver_with_a_reason_passes() -> None:
    assert problems([_CODE], _WAIVER, _DOCUMENTED) == []


def test_the_waiver_without_a_reason_fails() -> None:
    body = "## Design\n\nNo design change:\n"
    assert len(problems([_CODE], body, _DOCUMENTED)) == 1


def test_the_waiver_outside_the_design_section_fails() -> None:
    body = "## Why\n\nNo design change: a log message only.\n"
    assert len(problems([_CODE], body, _DOCUMENTED)) == 1


def test_the_placeholder_reason_is_not_a_waiver() -> None:
    body = "## Design\n\nNo design change: <reason>\n"
    assert len(problems([_CODE], body, _DOCUMENTED)) == 1


def test_a_waiver_inside_a_code_fence_is_not_a_waiver() -> None:
    body = "## Design\n\n```text\nNo design change: quoted, not stated.\n```\n"
    assert len(problems([_CODE], body, _DOCUMENTED)) == 1


def test_the_template_comment_is_not_a_waiver() -> None:
    body = "## Design\n\n<!-- or one line `No design change: <reason>` -->\n"
    assert len(problems([_CODE], body, _DOCUMENTED)) == 1


def test_another_modules_design_does_not_cover_this_one() -> None:
    other = "Docs/MODULES/bots/README.md"
    found = problems([_CODE, other], "", frozenset({"alerting", "bots"}))
    assert len(found) == 1 and "alerting" in found[0]


def test_each_owing_module_is_named() -> None:
    changed = [_CODE, "src/modules/bots/module.py"]
    assert len(problems(changed, "", frozenset({"alerting", "bots"}))) == 2


def test_a_module_without_a_design_folder_is_not_checked() -> None:
    assert problems(["src/modules/trading/module.py"], "", _DOCUMENTED) == []


def test_tests_and_docs_alone_are_not_checked() -> None:
    changed = ["tests/unit/modules/alerting/test_x.py", "Docs/README.md"]
    assert problems(changed, "", _DOCUMENTED) == []


def test_documented_modules_are_the_folders_under_docs_modules(tmp_path: Path) -> None:
    modules = tmp_path / "Docs" / "MODULES"
    (modules / "alerting").mkdir(parents=True)
    (modules / "README.md").write_text("x", encoding="utf-8")
    (modules / "bots.md").write_text("x", encoding="utf-8")
    assert documented_modules(tmp_path) == {"alerting"}


def test_the_repository_documents_alerting_as_a_folder() -> None:
    assert "alerting" in documented_modules(_ROOT)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],  # noqa: S607 - git on PATH
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_changed_paths_are_the_pull_requests_own(tmp_path: Path) -> None:
    """Three-dot: a commit on the base after the fork is not the pull request's."""
    _git(tmp_path, "init", "-q", "-b", "base")
    _git(tmp_path, "config", "user.email", "probe@example.invalid")
    _git(tmp_path, "config", "user.name", "probe")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "a")
    _git(tmp_path, "checkout", "-q", "-b", "head")
    (tmp_path / "pr.txt").write_text("pr", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "pr")
    head = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "checkout", "-q", "base")
    (tmp_path / "later.txt").write_text("later", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "later")
    base = _git(tmp_path, "rev-parse", "HEAD")
    assert changed_paths(base, head, tmp_path) == ["pr.txt"]


def test_a_file_moved_out_of_a_module_counts_for_that_module(tmp_path: Path) -> None:
    """A rename is listed under its old path too, so the module still owes its design."""
    _git(tmp_path, "init", "-q", "-b", "base")
    _git(tmp_path, "config", "user.email", "probe@example.invalid")
    _git(tmp_path, "config", "user.name", "probe")
    moved = tmp_path / "src" / "modules" / "alerting" / "hub.py"
    moved.parent.mkdir(parents=True)
    moved.write_text("class Hub:\n    pass\n" * 20, encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "a")
    base = _git(tmp_path, "rev-parse", "HEAD")
    _git(tmp_path, "mv", "src/modules/alerting/hub.py", "src/hub.py")
    _git(tmp_path, "commit", "-q", "-m", "move")
    head = _git(tmp_path, "rev-parse", "HEAD")
    changed = changed_paths(base, head, tmp_path)
    assert "src/modules/alerting/hub.py" in changed
    assert len(problems(changed, "", _DOCUMENTED)) == 1


def test_main_refuses_to_run_without_the_shas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BASE_SHA", raising=False)
    monkeypatch.delenv("HEAD_SHA", raising=False)
    assert check_design_in_step.main() == 2


def test_the_workflow_runs_the_check_with_the_pull_requests_shas() -> None:
    workflow = (_ROOT / ".github" / "workflows" / "commit-lint.yml").read_text(
        encoding="utf-8"
    )
    step = workflow[workflow.index("python3 scripts/check_design_in_step.py") - 400 :]
    for needed in ("PR_BODY:", "BASE_SHA:", "HEAD_SHA:"):
        assert needed in step, f"the design-in-step step lost {needed}"
    assert "fetch-depth: 0" in workflow, "a shallow checkout cannot diff base...head"
