# CS-006 — The comparison that compared itself

`EPIC-025` PR #226's `f76d5ced` claimed two Dev Board integration test failures were "confirmed
pre-existing" from a `git worktree` comparison against `master-warrior`. An independent PR review
reproduced both cleanly passing on `master-warrior` (3/3) and failing identically on the PR branch
(3/3), then traced the real cause: `6678d456`, the same PR, added a required `config_store`
argument to `ArmStrategyCommandHandler.__init__` and `tests/integration/presentation/ui/conftest.py:290`
was never updated to pass it. The regression was real and this PR's own; the "pre-existing" claim
was not, and shipped in a commit message before the review caught it.

## Why nothing caught it

| Net | Why it was silent | Still open? |
| :--- | :--- | :--- |
| The author's own "clean tree" comparison | Ran `PYTHONPATH=.. pytest <worktree>/tests/...` from the *original* checkout rather than from inside the worktree. Absolute imports resolve `Sagittarius_Elite_Warrior.src....` by searching `PYTHONPATH` for a directory of that name — `..` from the original checkout finds it there regardless of which tree the collected test *file* came from, so the comparison silently ran this PR's own `src/` against master's test files and reported "identical". No script, no path scan, no ratchet: a manual recipe with a footgun in it. | no — `scripts/verify_against_base.py` |
| CI itself | Correctly red on the branch both times it ran — the actual gate was never the blind spot; the false claim was in how the *author* read a correct red result. | n/a — CI was not silent here |

## The fix
- `scripts/verify_against_base.py`, in this same commit: names the comparison worktree exactly
  like the repository itself (`worktree_path()`) inside a fresh temporary parent, then runs pytest
  with `cwd` and `PYTHONPATH` both derived from that worktree — there is no path back to the
  original checkout's code left to fall into.
- `tests/unit/architecture/test_verify_against_base.py` pins the naming (E12: rename the worktree
  and both tests fail) and runs the script end to end against `HEAD`.

## Where else this is still open
- `ONBOARDING.md` §12.6's own A/B recipe (`git stash push -u` → run → `git stash pop` → run) does
  not have this bug — it never leaves the original checkout directory — but any future ad hoc
  `git worktree`-based comparison, in this repo or a session's own scratch work, repeats it unless
  it goes through `scripts/verify_against_base.py` instead of being hand-rolled again.
