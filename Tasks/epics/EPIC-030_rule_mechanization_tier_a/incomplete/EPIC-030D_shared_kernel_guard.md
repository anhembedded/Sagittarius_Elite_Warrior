# EPIC-030D — Domain, application and contracts import from the engine only the Shared Kernel

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟡 — A constructor change in the strategy module
**Complexity:** M — delivered in PR 2
**Epic:** [EPIC-030](../README.md)
**Depends on:** EPIC-030C

---

## 1. Context and problem
`architecture-rule.md` §3 limits the Shared Kernel to two engine symbols, but its guard scanned only indicator scripts; `src/modules/strategy/application/services/live_strategy_config_store.py:52` imported `sagittarius_engine.interfaces.i_config.IConfig` unnoticed and probed `save` with `getattr`.

## 2. Acceptance criteria
- [ ] A guard over `modules/*/{domain,application,contracts}` fails on any other engine import, including function-local ones.
- [ ] `LiveStrategyConfigStore` depends on `IConfigReader` and `IConfigWriter`; reverting it turns the guard red.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| Pending | Written when done. |

## 5. Testing
Not run. Each criterion maps to a unit test or guard under `tests/unit/`; documentation-only work names `python3 scripts/check_skill_prompt_references.py` and the document guards.

## Implementation notes (written when done)
Not yet established.
