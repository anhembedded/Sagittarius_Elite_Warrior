# EPIC-030B — Every rule clause names what enforces it, honestly

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟢 — Documentation only; a wrong tag misleads a reviewer
**Complexity:** S — delivered in PR 1 (documentation-only)
**Epic:** [EPIC-030](../README.md)
**Depends on:** EPIC-030A

---

## 1. Context and problem
`.claude/README.md` says every clause carries an enforcement tag, yet `ci-rule.md`, `commit-rule.md` and `report-rule.md` had none and 24 other clauses were untagged. Three `[gate]` tags claimed machine enforcement that does not exist (`code/quality.md` §1 zero `Any`, §5 no bare `noqa`), and four guard tags were malformed or pointed at prose.

## 2. Acceptance criteria
- [ ] `EPIC-030C`'s clause check reports zero untagged clauses.
- [ ] No `[gate]` tag claims a check that `pyproject.toml` or `ci-local.ps1` does not run.
- [ ] Every `[guard: …]` names one tracked test file.

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
