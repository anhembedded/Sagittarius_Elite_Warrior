# BOT-136 — Complete the workflow templates

**Status:** ✅ Done (2026-09-17)
**Source:** User, 2026-09-17: "ok, bổ sung cho tôi đi" ("Okay, add them for me"), accepting the template review.
**Risk:** 🟢 — Documentation formats and navigation only.
**Complexity:** `S` — Extend the existing formats without adding a new workflow.

## 1. Context and problem
The proposal workflow has no reusable format. Decision records mix approval with implementation, and tasks lack explicit acceptance criteria. Epic dependencies and bug reproduction evidence need clearer prompts.

## 2. Design
Add a proposal template and refine the five existing templates. Reuse the task format for epic children. Keep case studies within 35 lines and preserve the existing SPEC, pull-request and audit formats. A spike template is deferred until needed.

## 3. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/templates/proposal.md` | Add the proposal format. |
| `.claude/templates/task.md` | Acceptance criteria, dependencies and epic-child support. |
| `.claude/templates/decision.md` | Separate decision status, authority and implementation evidence. |
| `.claude/templates/bug-report.md` | Reproduction context, unknown states and verification evidence. |
| `.claude/templates/epic.md` | Dependencies and phase exit criteria. |
| `.claude/templates/case-study.md` | Follow-up references for remaining blind spots. |
| `.claude/README.md` | Usage guidance and regenerated inventory. |
| `.claude/ONBOARDING.md` | Route proposals to their format. |
| `CLAUDE.md` | Include proposals in format navigation. |
| `Tasks/ROADMAP.md` | Record completion and regenerate task counts. |

## 4. Testing
Run the reference checker and the five documentation guards required by ONBOARDING §7. Inspect the copied formats for ambiguous defaults and preserve the case-study section contract.

## Implementation notes

Added the proposal format and refined all five existing templates. Acceptance criteria now drive task verification; decisions distinguish acceptance, authority and implementation. Bug reports allow truthful unknown states and capture reproduction and post-fix evidence. Epics record dependencies and phase exits; case studies link remaining blind spots to tracked work. Navigation and the generated manifest are updated.

Verification: `python scripts/check_skill_prompt_references.py` passed for all 29 scanned documents. The five documentation guard modules named in ONBOARDING §7 passed: 112 tests, with one environment warning that pytest does not recognise the configured `timeout` option. No tests were added or changed. This documentation-only change does not require the runtime gate. Task counts were regenerated with `scripts/render_task_counts.py`.
