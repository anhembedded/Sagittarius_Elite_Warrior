"""`BUG-136` — `scripts/ci-local.ps1` silently tested the wrong checkout when
run from a worktree not literally named `Sagittarius_Elite_Warrior`, because
both the Python import scheme and this script's own pytest targets resolve
against that exact directory name (`install-rule.md` §2b). A worktree given
any other name — including `git worktree add ../review-worktree <sha>`,
which `pr-review/SKILL.md` §3 used to recommend — made pytest silently
resolve its hardcoded relative target against whichever OTHER sibling
happened to be named `Sagittarius_Elite_Warrior`, reporting a result for
that unrelated tree with no error at all.

These tests invoke the real script (not a reimplementation of its logic) in
two throwaway directory trees — one named to match, one not — and assert on
its own machine-readable `===CI_LOCAL_RESULT===` block, the same contract
`ci-rule.md` documents as the only trustworthy verdict. Same precedent as
`tests/unit/architecture/test_verify_against_base.py`'s fix for the sibling
defect in `scripts/verify_against_base.py`
(`Docs/CASE_STUDIES/CS-006_the_comparison_that_compared_itself.md`).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_PWSH = shutil.which("pwsh")
assert _PWSH is not None, "pwsh is not on PATH"

_SCRIPT_SOURCE = Path(__file__).resolve().parents[3] / "scripts" / "ci-local.ps1"


def _run_ci_local(checkout_dir: Path) -> subprocess.CompletedProcess[str]:
    scripts_dir = checkout_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    shutil.copy(_SCRIPT_SOURCE, scripts_dir / "ci-local.ps1")
    args = [
        _PWSH,
        "-NoProfile",
        "-File",
        "scripts/ci-local.ps1",
        "-SkipTests",
        "-SkipLint",
    ]
    return subprocess.run(
        args, cwd=checkout_dir, capture_output=True, text=True, timeout=60, check=False
    )


def _result_block(output: str) -> dict[str, str]:
    block = re.search(
        r"===CI_LOCAL_RESULT===(.*?)===END_CI_LOCAL_RESULT===", output, re.DOTALL
    )
    assert block is not None, f"no ===CI_LOCAL_RESULT=== block in output:\n{output}"
    fields: dict[str, str] = {}
    for line in block.group(1).strip().splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_mismatched_checkout_name_fails_fast_instead_of_silently_passing(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "review-worktree"  # the exact wrong name BUG-136 hit
    result = _run_ci_local(checkout)

    fields = _result_block(result.stdout)
    assert fields["RESULT"] == "FAIL"
    assert "Checkout Name" in fields["FAILED_STEPS"]
    assert result.returncode != 0
    assert "Sagittarius_Elite_Warrior" in result.stdout


def test_matching_checkout_name_is_unaffected(tmp_path: Path) -> None:
    checkout = tmp_path / "Sagittarius_Elite_Warrior"
    result = _run_ci_local(checkout)

    fields = _result_block(result.stdout)
    assert fields["RESULT"] == "PASS"
    assert fields["FAILED_STEPS"] == "none"
    assert result.returncode == 0


def test_case_only_mismatch_fails_fast(tmp_path: Path) -> None:
    # install-rule.md §2b names this exact scenario (a reviewer's default
    # lowercase clone) as the standard real-world trigger for this bug
    # class. PowerShell's `-eq` is case-insensitive, so a naive fix could
    # pass test_mismatched_checkout_name_fails_fast_instead_of_silently_passing
    # above while still missing this case; the guard must use `-ceq`.
    checkout = tmp_path / "sagittarius_elite_warrior"
    result = _run_ci_local(checkout)

    fields = _result_block(result.stdout)
    assert fields["RESULT"] == "FAIL"
    assert "Checkout Name" in fields["FAILED_STEPS"]
    assert result.returncode != 0
