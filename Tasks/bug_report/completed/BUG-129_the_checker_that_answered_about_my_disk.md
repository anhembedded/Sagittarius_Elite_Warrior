# BUG-129 — the reference checker answered about the developer's disk, and CI was red for 20 runs

- **Reported:** 2026-09-17 (found while reviewing `EPIC-025` PR 4.3l, from another session's
  commit `9a4a65d2` on `master-warrior`)
- **Severity:** High — not a user-facing defect, a **verification** defect: the local gate
  reported a step green while GitHub CI failed that same step, and because it runs before the
  tests, every later CI step was skipped. **Twenty consecutive red runs** landed on top of it.
- **Status:** ✅ Fixed 2026-09-17 — root-caused / reproduced / regression-tested (5 tests, red
  before the fix for the right reason) / verified by re-creating the silent condition

## Symptom

`scripts/check_skill_prompt_references.py` printed

    OK: every repository path referenced by 16 document(s) ... resolves.

on this machine, while GitHub CI on `master-warrior` failed the same script. **The timeline was
measured from the runs themselves rather than inherited**, and it is longer than commit
`9a4a65d2` (the other session's fix) states: the last green run is **370**, 2026-09-16 14:21 UTC.
Red begins at **371**, 14:49 UTC — the merge of PR 3.1c's documentation, the pull request whose own
message says *"`src/application/` is empty and gone from disk"*. Runs 371, 386 and 390 were read
directly; every completed run from 371 to 390 failed, which is **20 runs over about 11½ hours**,
not the three since 20:26 the fix commit names. Its output names four references:

    .agents/Skills/scout.prompt.md: src/domain/backtesting/
    .agents/Skills/scout.prompt.md: src/application/use_cases/
    .agents/Skills/sentinel.prompt.md: src/domain/backtesting/
    .agents/Skills/sentinel.prompt.md: src/application/use_cases/

## Root cause

`check()` resolved every cited path with `Path.exists()` — the **filesystem**, not the
repository. A working tree carries more than the repository does: `EPIC-025`'s moves deleted
`src/domain/backtesting/` and `src/application/use_cases/`, but every developer's tree kept them
alive as directories holding nothing but `__pycache__`, and nothing deletes those. So the
checker answered "yes, it exists" locally and "no" in CI, which clones fresh. CI was right.

The two prompts were the *symptom*. The mechanism is that a check whose answer depends on who
runs it is worse than no check, because it is believed.

## Fix

`_tracked_paths()` reads `git ls-files -z` once and adds every ancestor directory of every
tracked file, so a cited directory resolves from the files git holds inside it. `_resolves()`
consults that set; when git cannot answer (not a repository, git missing) it falls back to the
filesystem **and prints a warning naming this bug**, rather than degrading silently. The index
is read rather than a commit, because a staged-but-uncommitted move is real work and this
checker runs before that commit.

A second instance of the same disease was found by cleaning the stale directories off this
disk: `tests/unit/architecture/test_module_boundaries.py` required `src/application/` to exist
(`_ZONES_THAT_MUST_EXIST`), which no fresh clone has. It passed everywhere for the same wrong
reason, and CI never reached pytest to say so. That entry is retired, with the reason recorded
beside it, and `domain` is flagged as the next one to go.

**Run 390 proves that second half is the one CI is waiting on.** The other session's fix removed
the two prompts, so the reference check passed, pytest finally ran for the first time in 20 runs
— and failed on exactly this:

    FAILED tests/unit/architecture/test_module_boundaries.py::test_src_root_is_where_we_think_it_is
      - AssertionError: zone `application` missing under /home/runner/work/.../src
    1 failed, 4948 passed, 7 skipped

So the two halves of this bug were queued behind each other: the reference check hid the boundary
guard's identical false green for 11 hours by failing before pytest could run.

## The same fix one layer over

The two instances above are a script and one guard's constant. The *class* is any check that asks
the filesystem about repository content, and the registry of path-scanning guards is where that
class lives: `test_scanned_roots_are_not_empty.py` asserted each registered root "contains at
least one file of the kind the guard reads", by `rglob` — so a root surviving only as a
`__pycache__` shell reads as populated. It now filters those matches through `git ls-files`.

Measured before changing it, because a tightened guard that moves a ratchet is a different pull
request: filtering to tracked files flips **no** registered root from populated to empty today.
Verified by registering a root whose only file is untracked — it fails, and failed for the right
row. A sweep of this disk found **eight** stale directories git tracks nothing in (the
`order_book` pair from PR 4.1b, three under `tests/unit/application`, three under
`tests/unit/domain`); none is a registered root, so none was faking a green.

## Regression test

`tests/unit/architecture/test_skill_prompt_references_ask_git.py` — five tests, each building a
real tiny repository, because the bug is a disagreement between git's answer and the
filesystem's and a stubbed either-side cannot show them disagreeing. Two were red before the
fix (an untracked directory, then an untracked file, both reported as resolving); three pin the
fix against over-strictness: a tracked file resolves, a cited directory resolves from the files
tracked under it with or without its trailing slash, and a staged rename resolves.

Verified positively, not just by absence: re-creating the exact condition — `mkdir -p
src/application/use_cases/__pycache__` plus a rule file citing that path — now exits **1** and
names the reference, where before the fix it exited 0.

## Addendum — a second live instance, found by a second review

The claim above — "the class lives in the registry" — closed the registry and treated the class
as closed. It was not: `ONBOARDING.md` §7's required second-session review of the pull request
carrying this fix (PR #223) reproduced the exact shape on `test_module_boundaries.py`'s own zone
check, one function above the retired `application` entry. `git rm --cached` the file `domain`
tracks, leave the `__pycache__` shell on disk, and `test_src_root_is_where_we_think_it_is` kept
passing: `is_dir()` cannot tell a zone still holding real files from one surviving only as a
stale shell.

Fixed the same way, and the three now-duplicated copies of "read `git ls-files`" (the script's,
the registry's, and this one) collapsed into one shared `tests/unit/architecture/git_tracked_paths.py`,
which also gained the warning the registry's own copy had silently dropped when git could not
answer — a second finding from the same review. `CS-005` records both as the case study's own
"closed" line being wrong, corrected by the review process this bug's fix relied on working.

## Addendum — the warning itself was silent, found by a third review

A third independent-session review reproduced the second addendum's own fix as still silent, in a
way the first two reviews' checks did not surface: `warnings.warn()` fires when git is unavailable,
but neither of this repository's two failure-detection mechanisms sees a pytest warnings-summary
line — `grep -nE "FAILED|ERROR|Traceback|ResourceWarning"` (`CLAUDE.md`) and `ci-local.ps1`'s
`Invoke-RunLogScan`, which greps the structured `- (WARNING|ERROR|CRITICAL) -` app-log format.
Reproduced directly: `git` removed from `PATH`, both guards finished `130 passed, 81 warnings`,
exit 0. `git_tracked_paths.tracked_paths()` now raises `GitUnavailableError` instead of returning
`None` with a warning, so a caller's own test fails outright — pinned by `test_git_tracked_paths.py`
(5 tests, two of them E12 breaks on the real guards, not just on the shared function in isolation).

## Case study

[`CS-005`](../../../Docs/CASE_STUDIES/CS-005_the_check_that_asked_the_wrong_question.md) — the
gate was green, this check covered exactly this area, and it missed. Blind spots are never
local, so the case study lists where else the repository asks the filesystem a question only
git can answer.
