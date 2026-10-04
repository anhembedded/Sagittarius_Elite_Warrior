# EPIC-030A — The rule tree states one policy once and cites only sections that exist

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟢 — Documentation only; wording could change an agent's behaviour
**Complexity:** S — delivered in PR 1 (documentation-only)
**Epic:** [EPIC-030](../README.md)
**Depends on:** None

---

## 1. Context and problem
The 2026-10-04 audit found the gate policy restated eight times with two stale copies (`CLAUDE.md:43`, `.github/PULL_REQUEST_TEMPLATE.md:13` asked for a local full-gate log), dangling anchors (`ONBOARDING.md` §12.5, §12.3, `report-rule.md` §7, `ci-rule.md` §3a and §6), an invented quotation in `fix-bug/SKILL.md:27-28`, principle counts that disagree with the Constitution (`P1–P10`, `P1–P8`), rubric rows H1 and I1 contradicting their rules, three answers to Kanban versus Kanban plus Gantt, and twelve dated amendments inside rules. No definition of the documentation-only set existed outside rubric B3, and `master-warrior` accepted direct pushes.

## 2. Acceptance criteria
- [x] Every dangling section citation and the invented quotation are gone, checked by `EPIC-030C`'s checker.
- [x] `ONBOARDING.md` §7 defines the documentation-only set and forbids direct pushes to `master-warrior` (ruleset B1).
- [x] No rule, `ONBOARDING.md`, `CONSTITUTION.md` or `CLAUDE.md` holds a date or a PR number; history lives in the provenance ledger.
- [x] Rubric H1 and I1 agree with `ui-presentation-rule.md` §1 and `logging-rule.md` §1.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `CLAUDE.md`, `.github/PULL_REQUEST_TEMPLATE.md` | The full gate is GitHub Actions' `ci-local.ps1 -Full` run, not a local log |
| `.claude/ONBOARDING.md` | Documentation-only set defined; no direct push; dates moved to the ledger; check named `ci-local.ps1 -Full` |
| `.claude/rules/*.md`, skills, rubric H1/I1 | Dangling `§` anchors, the invented quote, principle counts and Kanban/Gantt contradictions fixed |
| `DECISION_2026-10-04_rule_provenance_ledger.md` | Provenance removed from rule text |

## 5. Testing
Documentation-only: `python3 scripts/check_skill_prompt_references.py` and the document guards (`test_claude_tree_is_wired.py`, `test_task_board_is_consistent.py`, `test_rule_navigation_is_complete.py`) passed on PR #322; the new checker reports no problem on the final tree.

## Implementation notes (written when done)
Delivered in pull request #322 and PR 3. Verification: the GitHub Actions `ci-local.ps1 -Full` run on each pull request head, read from its job log by the author and by an independent reviewer session per code pull request; `python3 scripts/check_skill_prompt_references.py` reports no problem over 43 prompt documents on the final tree.
