# EPIC-031A — Commit format and independent review are checked by CI

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "làm tiếp Tier B đi" (go on with Tier B), choosing commit lint and the review check, the engine pin and lockfile, and Claude Code hooks; mypy, ruff and the ratchets were not chosen.
**Risk:** 🟡 — a new required check can block merges until its first green run
**Complexity:** M
**Epic:** [EPIC-031](../README.md)
**Depends on:** EPIC-030

---

## 1. Context and problem
`commit-rule.md` §2 and `ONBOARDING.md` §7's independent review were rubric rows L1-L3 and a reviewer's discipline. Every session posts from the same GitHub account, so GitHub's required approvals cannot tell author from reviewer.

## 2. Acceptance criteria
- [x] The mechanism runs where the rule applies and refuses a breach with the rule it breaks.
- [x] Each mechanism carries a test that plants a breach and sees it refused.

## 3. Design
Stdlib scripts with a pure core and a thin I/O shell, so the decision is unit-tested and the workflow or hook only wires it.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `scripts/check_commit_messages.py`, `.github/workflows/commit-lint.yml` | Each commit a pull request adds: Conventional subject, allowed type, a body, the `Co-Authored-By:` and `Claude-Session:` trailers, a `fix:` citing its id |
| `scripts/check_independent_review.py`, `.github/workflows/independent-review.yml` | Sets the `independent-review` status from the newest trusted review of the head (owner, member or collaborator; verdict on its own line; coverage disclosure; a `Claude-Session:` no commit carries), failing when any commit lacks its session; documentation-only passes. The job is named `judge-review` so it can never stand in for the status |
| `scripts/rule_integrity/tags.py` | A gate step may live in a workflow or in `.claude/settings.json` |
| `.claude/skills/pr-review/SKILL.md`, `.claude/ONBOARDING.md` §7, commit and fix-bug rules | The reviewer writes the machine-read lines; the ruleset requires the checks; tags name the gates |

## 5. Testing
Unit: `tests/unit/scripts/test_check_commit_messages.py`, `test_check_independent_review.py`, the workflow-gate case in `rule_integrity/test_tags.py`. The commit check reports one problem over the last 149 non-merge commits (`d6a50ed`, empty body), which is a true one.

## Implementation notes (written when done)
Delivered in one pull request with the rest of EPIC-031; verification is that pull request's `ci-local.ps1 -Full` run and its independent review.
