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
| this very script, in the local gate | it asked the filesystem, not the repository | no — reads `git ls-files` now |
| the full local gate | it ran the script the same way, so it inherited the wrong answer | no, via the same fix |
| GitHub CI | it was **right**, unread for 20 runs; the first fix even mis-measured the window as three | **yes** — nothing reads CI's verdict for a branch just pushed |
| `test_module_boundaries.py`'s zone check | `is_dir()` has the same blind spot as `Path.exists()`; `domain` reproduced it identically to `application` | no — fixed below |
| this case study's own "closed" line | declared the class closed after one instance; the zone check was a second live instance | closed by a second session's review (`ONBOARDING.md` §7) |

## The fix

- `git_tracked_paths.py` (the script keeps its own copy — it must not import `tests/`) reads `git
  ls-files -z` plus every tracked file's ancestors; a caller gets `None` **and a warning naming
  this bug**, never a silent fallback, when git cannot answer. The registry
  (`test_scanned_roots_are_not_empty.py`) and the zone check (`test_module_boundaries.py`) both
  filter through it now instead of each keeping its own copy.
- `tests/unit/architecture/test_skill_prompt_references_ask_git.py` — five tests building a real
  repository, since stubbing either side cannot show git and the filesystem disagreeing.

## Where else this is still open

- **Any check that asks the filesystem about repository content, in general.** Two are closed
  above; `tests/unit/test_logging_namespace_guard.py` is not, on purpose — scanning every `.py`
  on disk, tracked or not, catches a bad name before a commit rather than a false green.
- **A local gate cannot see a red CI.** The habit this cost: after pushing, read the run.
