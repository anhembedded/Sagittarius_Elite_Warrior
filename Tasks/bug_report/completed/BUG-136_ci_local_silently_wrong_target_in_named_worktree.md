# BUG-136 — `ci-local.ps1` silently tests the wrong checkout inside a review worktree

- **Reported:** 2026-09-25 (by an independent reviewer session, during re-review of `PR #266`)
- **Severity:** 🟡 P2 — a full-gate run can silently report a false PASS (or run against stale code) for any reviewer following this repo's own recommended isolated-worktree pattern; does not affect a normal in-place checkout.
- **Status:** Fixed (2026-09-25)
- **Context:** Independent PR review workflow (`.claude/skills/pr-review/SKILL.md` §3 "Isolated Worktree Verification") → `scripts/ci-local.ps1` (test-tier target resolution).
- **Environment:** Any checkout where the repository directory is not literally named `Sagittarius_Elite_Warrior` — in particular, `git worktree add ../review-worktree <sha>`, the exact command `pr-review/SKILL.md` line 34 recommends.

## Reproduction

1. From a normal checkout at `.../Sagittarius_Elite_Warrior`, create a worktree the way `pr-review/SKILL.md` §3 tells a reviewer to: `git worktree add ../review-worktree <COMMIT_SHA>`.
2. `cd ../review-worktree` and run `pwsh -NoProfile -File scripts/ci-local.ps1 -Full`.
3. Expected: the gate runs against the worktree's own tree (the commit just checked out).
4. Actual: `scripts/ci-local.ps1` builds its pytest target as the **literal string** `"Sagittarius_Elite_Warrior/tests"` (and `.../tests/unit`, `.../tests/sanity`, `.../tests/testnet`), then runs pytest from `$repoRoot` (the worktree's own root, e.g. `.../review-worktree`). Since the worktree directory is not named `Sagittarius_Elite_Warrior`, that relative path does not exist inside the worktree — pytest instead resolves it against whatever directory of that exact name happens to sit as a sibling on disk (in the reviewer's case, the original, differently-committed checkout). The gate reports a result for that **other** tree, not the worktree just created, with no error and no warning.

## Symptom

Reported directly by the reviewer session that hit this (PR #266, comment https://github.com/anhembedded/Sagittarius_Elite_Warrior/pull/266#issuecomment-5827142674): "the first gate attempt used an isolated `git worktree` ... which produced a false `Ruff Lint` failure — `scripts/ci-local.ps1` hardcodes its pytest target as the literal path `Sagittarius_Elite_Warrior/tests`, so a worktree not named exactly `Sagittarius_Elite_Warrior` silently ran against the sibling checkout instead of itself." The reviewer caught it only because the result didn't match expectations and re-ran directly against the real checkout instead; a reviewer who did not notice the mismatch would have published a gate result for the wrong commit.

## Root cause

`scripts/ci-local.ps1:206-208` and `:410` build the pytest target as the literal, non-relative-to-`$PSScriptRoot` string `"Sagittarius_Elite_Warrior/tests"` (and its `unit`/`sanity`/`testnet` children), documented at `:344-347` as a deliberate assumption: "the repo directory is expected to already be named `Sagittarius_Elite_Warrior` ... so running pytest from `$repoRoot` with target `Sagittarius_Elite_Warrior/tests` resolves against the real directory — no `.venv_alias` symlink needed." That assumption is correct for a normal clone but false for any worktree given a different name — including the exact one `.claude/skills/pr-review/SKILL.md:34` tells a reviewer to create (`git worktree add ../review-worktree <sha>`). The script never checks that `$repoRoot`'s own basename matches the literal it is about to concatenate, so a mismatch fails silently (pytest happily finds *a* `tests/` directory, just not the intended one) rather than erroring.

## Fix

Both candidates implemented, since neither alone is complete:

1. **`scripts/ci-local.ps1`** — a precondition check right after `$botRoot`/`$repoRoot` are computed: if `Split-Path -Leaf $botRoot` is not exactly `Sagittarius_Elite_Warrior`, print a clear, actionable explanation (why — the import scheme and this script's own targets both resolve against that literal name — and how to fix it) and force `$SkipLint`/`$SkipTests` to `$true`, adding `"Checkout Name"` to `$failed`. Deliberately **not** a bare `exit`/`throw`: the script still reaches its normal end and prints the real `===CI_LOCAL_RESULT===`/`===END_CI_LOCAL_RESULT===` block (`ci-rule.md`'s own documented verdict contract) with `RESULT: FAIL`, so a caller waiting specifically for that marker is never left hanging, and a human/agent reading truncated output still sees a correct FAIL rather than the old silent PASS.
2. **`.claude/skills/pr-review/SKILL.md` §3** — while implementing (1), found this repo already has the complete, correct fix for the identical class of defect in a sibling script: `scripts/verify_against_base.py`'s `worktree_path()` (`Docs/CASE_STUDIES/CS-006_the_comparison_that_compared_itself.md`) names its comparison worktree exactly `Sagittarius_Elite_Warrior` inside a **fresh temporary parent** — never `../`, which risks colliding with an existing, differently-committed sibling of that same name (exactly what put BUG-136's own reproduction into a silent-wrong-tree state rather than an immediate import error). Updated §3's recommended worktree recipe to the same pattern (`mktemp -d` parent + a worktree literally named `Sagittarius_Elite_Warrior` inside it), so a reviewer following this repo's own documented workflow no longer hits BUG-136 at all — (1) is then defense in depth for anyone who still hand-rolls a mismatched worktree name.

## Regression test

`tests/unit/scripts/test_ci_local_checkout_name_guard.py` (new, +2) — invokes the real `scripts/ci-local.ps1` (not a reimplementation) inside two throwaway directory trees, one named `review-worktree` (the exact reproduction case) and one named `Sagittarius_Elite_Warrior`, and asserts on the script's own machine-readable `===CI_LOCAL_RESULT===` block: the mismatched case must report `RESULT: FAIL` / `FAILED_STEPS: Checkout Name`, the matching case must be unaffected (`RESULT: PASS` / `FAILED_STEPS: none`). Mutation-verified: reverting `$checkoutNameValid` to a hardcoded `$true` (simulating the pre-fix behavior) sent the mismatched-case test red for the right reason (`RESULT` was `PASS`, expected `FAIL`); restored after confirming.

## Verification

`ruff check`/`ruff format --check` clean on the new test file. `tests/unit/scripts/test_ci_local_checkout_name_guard.py`: 2 passed. `tests/unit/architecture`: 440 passed, no regressions. `python3 scripts/check_skill_prompt_references.py`: OK. Manually reproduced both before (silent wrong-tree PASS, matching the original report) and after (loud `RESULT: FAIL`) in a throwaway `/tmp` directory tree mirroring the bug's own reproduction steps, and confirmed a normal, correctly-named run of this repository's own real gate (`ci-local.ps1 -SkipTests`) is unaffected (`RESULT: PASS`).

## Suggested next steps

None — both candidates shipped together, since (1) alone would have left `pr-review/SKILL.md`'s own recommended workflow still hitting the defect it now silently reports for correctly (a real fix, just no longer a *silent* one), and (2) alone would have left any hand-rolled or agent-authored worktree command outside this one skill file still exposed.
