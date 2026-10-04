# EPIC-031C — Two agent rules are barriers in the tool itself

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "làm tiếp Tier B đi" (go on with Tier B), choosing commit lint and the review check, the engine pin and lockfile, and Claude Code hooks; mypy, ruff and the ratchets were not chosen.
**Risk:** 🟡 — a new required check can block merges until its first green run
**Complexity:** S
**Epic:** [EPIC-031](../README.md)
**Depends on:** EPIC-030

---

## 1. Context and problem
"Never judge a run by its console tail" and "never commit over a red check" relied on the agent remembering them.

## 2. Acceptance criteria
- [x] The mechanism runs where the rule applies and refuses a breach with the rule it breaks.
- [x] Each mechanism carries a test that plants a breach and sees it refused.

## 3. Design
Stdlib scripts with a pure core and a thin I/O shell, so the decision is unit-tested and the workflow or hook only wires it.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/hooks/pre_tool_use.py` | Refuses a pwsh run of the gate piped into `tail`; runs ruff, format and the rule checker before `git commit` and refuses a red result |
| `.claude/settings.json` | Registers the hook; asks before editing `requirements.*`, `engine.ref`, `pyproject.toml` or the settings |
| `ci-rule.md`, `commit-rule.md` | Tags name the hook as a gate |

## 5. Testing
Unit: `tests/unit/scripts/test_pre_tool_use_hook.py`. The installed hook refused a piped gate run with exit code 2; its first live run also refused prose that merely named the pattern, so the pattern now requires a pwsh invocation (probe added).

## Implementation notes (written when done)
Delivered in one pull request with the rest of EPIC-031; verification is that pull request's `ci-local.ps1 -Full` run and its independent review.
