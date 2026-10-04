# EPIC-030E — Inside one module, dependencies point inward

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟢 — None beyond a new allowlist
**Complexity:** S — delivered in PR 2
**Epic:** [EPIC-030](../README.md)
**Depends on:** EPIC-030C

---

## 1. Context and problem
`tests/unit/architecture/boundaries/rules.py:90` allows every import inside one module, so domain to ui or application to ui went unchecked; one deliberate lazy import exists (`strategy_chart_overlay_service.py:55`). Contracts importing their own domain is a documented decision (`i_sizing_policy.py:131-134`) and stays allowed.

## 2. Acceptance criteria
- [x] A guard refuses domain to application/adapters/ui/composition/cli and application to ui/adapters/composition/cli inside one module, with a shrink-only allowlist of one entry.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/architecture/boundaries/layers.py`, `scan.py` | Layer predicate and `find_layer_violations` |
| `tests/unit/architecture/test_module_layers_point_inward.py`, `allowlist_module_layers.txt` | New guard with a one-entry shrink-only allowlist |

## 5. Testing
Architecture guard plus rule-table rows; adding an outward import turns it red (confirmed by the reviewer).

## Implementation notes (written when done)
Delivered in pull request #323. Verification: the GitHub Actions `ci-local.ps1 -Full` run on each pull request head, read from its job log by the author and by an independent reviewer session per code pull request; `python3 scripts/check_skill_prompt_references.py` reports no problem over 43 prompt documents on the final tree.
