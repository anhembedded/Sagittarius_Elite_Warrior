# EPIC-032A — Mypy checks what the config says it checks

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "làm tiếp phần còn lại của Tier B đi" (do the rest of Tier B): the mypy, ruff and ratchet items of the audit's Tier B, which EPIC-031 left out.
**Risk:** 🟢 — measured green before it was enabled
**Complexity:** S
**Epic:** [EPIC-032](../README.md)
**Depends on:** EPIC-031

---

## 1. Context and problem
The strict overrides for Domain and Application targeted `src.domain.*` and `src.application.*`; `EPIC-025` moved both layers under `src/modules/*/`, so the strict check covered no file and mypy, without `warn_unused_configs`, said nothing. The 69-pattern `exclude` list had no guard against growth, and three of its patterns matched no file.

## 2. Acceptance criteria
- [x] The check runs in the commit tier or the unit tier and fails on a planted breach.
- [x] The tree is green under it on the day it lands, with no new suppression.

## 3. Design
Enable what the tree already meets; ratchet what it does not, per file, so a fix elsewhere cannot pay for a new breach.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `pyproject.toml` | `warn_unused_configs = true`; Domain, Application and the carve-outs retargeted to `src.modules.*`; three dead `exclude` patterns removed |
| `src/modules/trading/application/account_control/futures_settings_service.py` | `_result` is generic, so its result keeps its type argument |
| `src/modules/bots/application/services/grid_executor.py` | Re-reads the state after `reconciler.run()` moves it, where the checker kept it narrowed |
| `tests/unit/architecture/test_mypy_scope_only_shrinks.py`, `baseline_mypy_excludes.txt` | `exclude` only shrinks and matches files; every first-party override matches a module |

## 5. Testing
Retargeting turned on strict checking for every module's domain and application layers: two errors, both fixed, none suppressed. Unit: the guard's own probes, including a moved tree whose override matches nothing.

## Implementation notes (written when done)
Delivered in one pull request with the rest of EPIC-032; verification is that pull request's `ci-local.ps1 -Full` run and its independent review.
