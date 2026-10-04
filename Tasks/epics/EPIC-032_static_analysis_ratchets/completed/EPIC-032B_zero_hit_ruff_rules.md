# EPIC-032B — Four ruff rules the tree already meets refuse the first breach

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "làm tiếp phần còn lại của Tier B đi" (do the rest of Tier B): the mypy, ruff and ratchet items of the audit's Tier B, which EPIC-031 left out.
**Risk:** 🟢 — measured green before it was enabled
**Complexity:** S
**Epic:** [EPIC-032](../README.md)
**Depends on:** EPIC-031

---

## 1. Context and problem
`BLE001`, `PGH003`, `PGH004`, `TRY203` and `PLR0904` measured zero hits, yet `code/errors.md` and `code/quality.md` clauses they serve were review-only.

## 2. Acceptance criteria
- [x] The check runs in the commit tier or the unit tier and fails on a planted breach.
- [x] The tree is green under it on the day it lands, with no new suppression.

## 3. Design
Enable what the tree already meets; ratchet what it does not, per file, so a fix elsewhere cannot pay for a new breach.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `pyproject.toml` | Four codes join `extend-select`; `PLR0904`, measured at zero only because it is a preview rule ruff never ran, goes to EPIC-032C's ratchet |
| `.claude/rules/code/errors.md`, `.claude/rules/code/quality.md` | Clauses tagged with the ruff codes that now enforce them (`S110`, `B904` were already selected) |

## 5. Testing
`ruff check src tests tools scripts` stays clean with the rules enabled; the rule checker resolves every new `[gate: ruff …]` tag against `pyproject.toml`.

## Implementation notes (written when done)
Delivered in one pull request with the rest of EPIC-032; verification is that pull request's `ci-local.ps1 -Full` run and its independent review.
