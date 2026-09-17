# CS-005 — the check that asked the wrong question

`BUG-129`: `scripts/check_skill_prompt_references.py` resolved cited paths with `Path.exists()`,
so it answered about the disk it ran on. `EPIC-025` deleted two legacy directories (named in that
bug report) and left them on every machine as shells holding nothing but `__pycache__`, which
nothing deletes. Gone from the repository, present on disk: local gate green, GitHub CI red from
run 371 (2026-09-16 14:49 UTC). This script runs *before* the tests, so every later step was
skipped and **20 runs went red over ~11½ hours** — including the four that closed PR 4.3.

## Why nothing caught it

| Net | Why it was silent | Still open? |
| :--- | :--- | :--- |
| this script, in the local gate | asked the filesystem, not the repository | no — reads `git ls-files` |
| GitHub CI | it was **right**, unread for 20 runs | **yes** — nothing reads CI's verdict for a fresh push |
| `test_module_boundaries.py`'s zone check | `is_dir()` has `Path.exists()`'s blind spot | no — fixed below |
| the first fix's own warning | fired, but a pytest warnings line is invisible to this repo's two failure checks (`grep`, `Invoke-RunLogScan`) — a round-2 review reproduced it as `130 passed, exit 0` | no — raises now |
| this case study's own "closed" line, twice | closed the class after one instance, then claimed a warning that proved nothing failed | closed by two independent-session reviews (`ONBOARDING.md` §7) |

## The fix

- `git_tracked_paths.py` (the script keeps its own copy — must not import `tests/`) reads `git
  ls-files -z` and **raises**, naming this bug, when git cannot answer — never `None` plus a
  warning nothing reads. The registry and the zone check both filter through it.
- `test_skill_prompt_references_ask_git.py` and `test_git_tracked_paths.py` (5 tests each, the
  raise pinned via E12 on both real guards) build a real repository, since a stub cannot show git
  and the filesystem disagreeing.

## Where else this is still open

- **Any check asking the filesystem about repository content, in general.** Three closed above;
  `tests/unit/test_logging_namespace_guard.py` is not, on purpose — it scans every `.py` on disk,
  tracked or not, to catch a bad name before a commit.
- **A local gate cannot see a red CI.** The habit this cost: after pushing, read the run.
- **A warning is not a failure** by this repo's own two mechanisms — raise, don't warn.
