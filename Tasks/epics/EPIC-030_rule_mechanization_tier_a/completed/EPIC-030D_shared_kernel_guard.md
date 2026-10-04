# EPIC-030D — Domain, application and contracts import from the engine only the Shared Kernel

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟡 — A constructor change in the strategy module
**Complexity:** M — delivered in PR 2
**Epic:** [EPIC-030](../README.md)
**Depends on:** EPIC-030C

---

## 1. Context and problem
`architecture-rule.md` §3 limits the Shared Kernel to two engine symbols, but its guard scanned only indicator scripts; `src/modules/strategy/application/services/live_strategy_config_store.py:52` imported `sagittarius_engine.interfaces.i_config.IConfig` unnoticed and probed `save` with `getattr`.

## 2. Acceptance criteria
- [x] A guard over `modules/*/{domain,application,contracts}` fails on any other engine import, including function-local ones.
- [x] `LiveStrategyConfigStore` depends on `IConfigReader` and `IConfigWriter`; reverting it turns the guard red.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/strategy/application/services/live_strategy_config_store.py` | Depends on `IConfigReader`/`IConfigWriter`; `getattr` probe removed |
| `tests/unit/architecture/test_module_inside_imports_only_the_shared_kernel.py` | New guard |
| `tests/unit/architecture/boundaries/imports.py`, `rules.py` | Shared runtime-import walker and `SHARED_KERNEL_MODULES` |

## 5. Testing
Architecture guard plus probes; reverting the store fix turns it red (PR #323 review, mutation confirmed by the reviewer).

## Implementation notes (written when done)
Delivered in pull request #323. Verification: the GitHub Actions `ci-local.ps1 -Full` run on each pull request head, read from its job log by the author and by an independent reviewer session per code pull request; `python3 scripts/check_skill_prompt_references.py` reports no problem over 43 prompt documents on the final tree.
