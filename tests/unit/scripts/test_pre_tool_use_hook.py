"""`EPIC-031C` — the Bash PreToolUse hook refuses `ci-local | tail` and a commit over a red check."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import repo_root

_HOOK = repo_root() / ".claude" / "hooks" / "pre_tool_use.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("pre_tool_use_hook", _HOOK)
    if spec is None or spec.loader is None:
        raise ImportError(_HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load()


def _bash(command: str) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def _green(argv: list[str], root: Path) -> tuple[int, str]:
    return 0, ""


def _red(argv: list[str], root: Path) -> tuple[int, str]:
    return 1, "E501 something is wrong"


@pytest.mark.parametrize(
    "command",
    [
        "pwsh -NoProfile -File scripts/ci-local.ps1 -Full | tail -20",
        "pwsh -File scripts/ci-local.ps1 -Full 2>&1 | grep -v x | tail",
    ],
)
def test_piping_the_gate_into_tail_is_refused(command: str, tmp_path: Path) -> None:
    assert "LOG_FILE" in (hook.decide(_bash(command), tmp_path, _green) or "")


def test_prose_that_names_the_pattern_is_not_refused(tmp_path: Path) -> None:
    command = "cat > notes.md <<'EOF'\nRefuses `ci-local.ps1 … | tail`\nEOF"
    assert hook.decide(_bash(command), tmp_path, _green) is None


def test_a_quoted_invocation_inside_a_heredoc_is_not_refused(tmp_path: Path) -> None:
    """PR #326 review finding 5: a script whose string literal holds the pattern."""
    command = "cat > probe.py <<'EOF'\nCMD = 'pwsh -File ci-local.ps1 | tail'\nEOF"
    assert hook.decide(_bash(command), tmp_path, _green) is None


def test_a_gate_run_after_a_separator_is_refused(tmp_path: Path) -> None:
    command = "cd repo && pwsh -File scripts/ci-local.ps1 -Full | tail -3"
    assert hook.decide(_bash(command), tmp_path, _green) is not None


def test_reading_the_log_file_with_tail_is_allowed(tmp_path: Path) -> None:
    command = (
        "pwsh -File scripts/ci-local.ps1 -Full > /tmp/ci.log 2>&1; tail -5 notes.txt"
    )
    assert hook.decide(_bash(command), tmp_path, _green) is None


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'x'",
        "git add -A && git commit -q -F -",
        "git -C repo commit -m x",
    ],
)
def test_a_commit_over_a_red_check_is_refused_with_its_output(
    command: str, tmp_path: Path
) -> None:
    refusal = hook.decide(_bash(command), tmp_path, _red)
    assert refusal is not None
    assert "E501 something is wrong" in refusal


def test_a_commit_over_green_checks_runs(tmp_path: Path) -> None:
    assert hook.decide(_bash("git commit -m x"), tmp_path, _green) is None


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git log --oneline",
        "echo commit",
        'echo "remember to git commit"',
        "git commit-tree HEAD^{tree} -m x",
    ],
)
def test_other_commands_never_run_the_checks(command: str, tmp_path: Path) -> None:
    assert hook.decide(_bash(command), tmp_path, _red) is None


def test_a_missing_ruff_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PR #326 review finding 6: no ruff means a refused commit, never a skipped check."""
    monkeypatch.setattr(hook.shutil, "which", lambda name: None)
    checks = hook.commit_checks(tmp_path)
    assert checks[0][0] == "ruff"
    code, _ = hook.run(checks[0][1], tmp_path)
    assert code != 0


def test_other_tools_pass_through(tmp_path: Path) -> None:
    event = {"tool_name": "Edit", "tool_input": {"command": "git commit"}}
    assert hook.decide(event, tmp_path, _red) is None
