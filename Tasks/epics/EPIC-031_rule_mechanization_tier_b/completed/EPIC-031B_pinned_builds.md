# EPIC-031B — Two runs of one commit build the same thing

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "làm tiếp Tier B đi" (go on with Tier B), choosing commit lint and the review check, the engine pin and lockfile, and Claude Code hooks; mypy, ruff and the ratchets were not chosen.
**Risk:** 🟡 — a new required check can block merges until its first green run
**Complexity:** S
**Epic:** [EPIC-031](../README.md)
**Depends on:** EPIC-030

---

## 1. Context and problem
CI cloned the engine's moving `main` (`ci.yml`) and installed loose requirements, so an upstream push could change a run of an unchanged commit.

## 2. Acceptance criteria
- [x] The mechanism runs where the rule applies and refuses a breach with the rule it breaks.
- [x] Each mechanism carries a test that plants a breach and sees it refused.

## 3. Design
Stdlib scripts with a pure core and a thin I/O shell, so the decision is unit-tested and the workflow or hook only wires it.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `engine.ref` | The engine commit every environment installs |
| `requirements.lock` | Every transitive version, `uv pip compile --universal`; it matches the venv that passed every tier |
| `.github/workflows/ci.yml` | Fetches the pinned engine commit and installs the lock |
| `.claude/rules/install-rule.md` | Install and bump instructions |

## 5. Testing
Unit: `tests/unit/scripts/test_dependency_pins.py`. The pinned fetch was run and checks out `72e4042`.

## Implementation notes (written when done)
Delivered in one pull request with the rest of EPIC-031; verification is that pull request's `ci-local.ps1 -Full` run and its independent review.
