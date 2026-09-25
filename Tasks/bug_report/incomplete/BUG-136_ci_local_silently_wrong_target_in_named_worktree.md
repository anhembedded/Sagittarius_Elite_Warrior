# BUG-136 — `ci-local.ps1` silently tests the wrong checkout inside a review worktree

- **Reported:** 2026-09-25 (by an independent reviewer session, during re-review of `PR #266`)
- **Severity:** 🟡 P2 — a full-gate run can silently report a false PASS (or run against stale code) for any reviewer following this repo's own recommended isolated-worktree pattern; does not affect a normal in-place checkout.
- **Status:** Open
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

Not yet implemented. Two independent, non-exclusive candidates for whoever picks this up:
1. In `ci-local.ps1`, derive the target from `$repoRoot`'s actual directory name (`Split-Path -Leaf $repoRoot`) instead of the hardcoded literal, or fail fast with a clear error when the basename does not match `Sagittarius_Elite_Warrior`.
2. In `pr-review/SKILL.md` §3, change the recommended worktree command to name the directory `Sagittarius_Elite_Warrior` (e.g. `git worktree add ../Sagittarius_Elite_Warrior-review <sha>` is not enough either — the leaf name itself must be exactly `Sagittarius_Elite_Warrior`, e.g. as a sibling under a differently-named parent), or document the caveat prominently until (1) ships.

## Regression test

Not yet written. Candidate: a test that constructs `ci-local.ps1`'s target strings from an actual `$repoRoot` whose leaf directory name is deliberately *not* `Sagittarius_Elite_Warrior` (e.g. a temp dir), and asserts either the script errors clearly or resolves the target correctly relative to that root — not silently against an unrelated sibling.

## Verification

Not run — no fix implemented yet.

## Suggested next steps

Pick candidate 1 (fix the script itself) as the durable fix, since candidate 2 (renaming the worktree) only works as long as every reviewer remembers the caveat and the parent directory has no other `Sagittarius_Elite_Warrior`-named sibling to collide with instead. Small, bounded, no dependency.
