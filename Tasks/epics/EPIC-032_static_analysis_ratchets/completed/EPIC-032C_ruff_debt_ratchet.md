# EPIC-032C — Four ruff rules the tree cannot meet yet only lose violations

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "làm tiếp phần còn lại của Tier B đi" (do the rest of Tier B): the mypy, ruff and ratchet items of the audit's Tier B, which EPIC-031 left out.
**Risk:** 🟢 — measured green before it was enabled
**Complexity:** M
**Epic:** [EPIC-032](../README.md)
**Depends on:** EPIC-031

---

## 1. Context and problem
`ANN401`, `PLC0415`, `C901` and `T20` had too many hits to enable and no limit, so each count could only grow.

## 2. Acceptance criteria
- [x] The check runs in the commit tier or the unit tier and fails on a planted breach.
- [x] The tree is green under it on the day it lands, with no new suppression.

## 3. Design
Enable what the tree already meets; ratchet what it does not, per file, so a fix elsewhere cannot pay for a new breach.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/architecture/test_ruff_debt_only_shrinks.py`, `baseline_ruff_debt.json` | Hits per rule and file; a count may only fall, and a fixed hit must lower its line |
| `tests/unit/architecture/scanned_roots_registry.py`, `test_guard_scans_its_registered_root.py` | Both new guards registered |
| `.claude/rules/code/quality.md`, `.claude/rules/commit-rule.md` | Clauses name the ratchet |

## 5. Testing
Baseline in the code trees: ANN401 135 hits in 45 files, PLC0415 45 in 18, C901 17 in 17; T20 247 in 54 across all trees. A `print` planted in `src/core/repo_root.py` failed the guard naming that file.

## Implementation notes (written when done)
Delivered in one pull request with the rest of EPIC-032; verification is that pull request's `ci-local.ps1 -Full` run and its independent review.
