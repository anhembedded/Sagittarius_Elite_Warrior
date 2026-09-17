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
| this very script, in the local gate | it asked the filesystem. A working tree is not the repository, and the difference is exactly what a move leaves behind | no — it reads `git ls-files` now |
| the full local gate, four runs across three pull requests | it runs the script the same way, so it inherited the same wrong answer: a gate is only as honest as its narrowest check | no, via the same fix |
| GitHub CI | it was **right** and nobody read it for 20 runs. Worse, the first session to look inherited the timeline from the newest runs and recorded it as three; reading run 371 is what found the other seventeen | **yes**: nothing in the local workflow reads CI's verdict for the branch it just pushed |
| `tests/unit/architecture/test_module_boundaries.py` | it *required* the deleted application zone to exist, so it carried the same false green — and CI never reached pytest to say so, the two failures queued behind each other for 11 hours | no — that entry is retired, `domain` flagged as next |
| the review checklist `.claude/skills/pr-review/SKILL.md` §B | it asks whether the log was scanned, never whether the tree the gate ran on is the tree a clone would get | **yes** |

## The fix

- `_tracked_paths()` reads `git ls-files -z` and adds every ancestor of every tracked file, so a
  cited directory resolves from what git holds inside it. Where git cannot answer, the filesystem
  fallback **prints a warning naming this bug** rather than degrading quietly.
- `tests/unit/architecture/test_skill_prompt_references_ask_git.py` — five tests, each building a
  real repository, since stubbing either side cannot show git and the filesystem disagreeing.
- `_ZONES_THAT_MUST_EXIST` drops the zone the epic deleted, reason recorded in place.

## Where else this is still open

- ~~**Any check that asks the filesystem about repository content.**~~ Closed for the registry:
  `test_scanned_roots_are_not_empty.py` filters its matches through `git ls-files`, so a root alive
  only as a shell reads as empty. Eight stale directories sat on this disk — they survive `git rm`
  whenever they still hold ignored files — and none of them was a registered root.
- **A local gate cannot see a red CI.** The habit this cost: after pushing, read the run.
