# EPIC-030M — Tests never write into the repository's state or database

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🔴 — A cross-cutting path seam in `core`
**Complexity:** M — delivered in PR 3
**Epic:** [EPIC-030](../README.md)
**Depends on:** None

---

## 1. Context and problem
Integration and sanity runs wrote `<repo>/state/ui_state.json`, `<repo>/state/bots` (whose restore resumes RUNNING bots), trading checkpoints and `<repo>/database`, through `repo_state_store_locator.py:36-43`, `trading/composition/adapter_bindings.py:136-140`, `bots/composition/state_bindings.py:38-42` and the relative `database.dir`.

## 2. Acceptance criteria
- [ ] With `SEW_DATA_ROOT` unset every production path is unchanged; with it set every one moves under it.
- [ ] A full unit, integration and sanity run creates neither `<repo>/state` nor `<repo>/database`.

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
