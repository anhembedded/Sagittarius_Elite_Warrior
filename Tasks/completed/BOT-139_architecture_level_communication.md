# BOT-139 — Communicate at the architecture and delivery level

**Status:** ✅ Done (2026-09-17)
**Source:** User, 2026-09-17: "nói chuyện như nó với SA, High levle maganer, không show implement khi không yêu cầu" ("Speak to me as a solution architect and high-level manager; do not show implementation unless requested").
**Risk:** 🟢 — Communication rules and review/report instructions only.
**Complexity:** S — Refine the existing reporting authority and align its callers.
**Depends on:** None.

## 1. Context and problem
Reports still encourage technical evidence dumps and fixed diagram/table forms. The user needs architectural consequences, delivery confidence and decisions, while implementation evidence remains available for engineering work.

## 2. Acceptance criteria
- [x] Default conversation to outcomes, system responsibilities, trade-offs, material risks and recommendations.
- [x] Keep implementation details out of routine chat unless requested or needed to explain a consequential decision; preserve full technical evidence in the existing record.
- [x] Align task and review reporting without weakening defect disclosure or the mandatory validated epic Kanban.
- [x] Pass document guards and reference checks without increasing the always-loaded ceiling.

## 3. Design
Rewrite the existing reporting rule as the single communication authority. Retain numbered sections cited by other workflows. Apply the same audience contract to task handoff and the review skill, while the reviewer still supplies technical findings to its requesting agent. No new persona skill or parallel report store.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/rules/report-rule.md` | Audience, information level, evidence, recommendations and decisions. |
| `.claude/rules/report-task-rule.md` | Outcome-oriented progress and concise acceptance/delivery evidence. |
| `.claude/skills/pr-review/SKILL.md` | Separate user summary from actionable engineering findings. |
| `.claude/agents/reviewer.md` | Clarify the recipient of detailed findings. |
| `.claude/ONBOARDING.md` | Route communication to the revised rule. |
| `.claude/README.md` | Regenerate the manifest. |
| `Tasks/ROADMAP.md` | Task entry and derived counts. |

## 5. Testing
Inspect instruction consistency for routine updates, architectural decisions, blocked acceptance and requested technical reviews. Run ONBOARDING §7's documentation guards, reference checker and the review-skill validator.

## Implementation notes

Updated the existing reporting authority rather than adding a persona layer. Routine conversation now leads with outcomes and architecture/delivery consequences. Details are included on request or when essential to a decision. Recommendations include reasons and trade-offs; material risks and uncertainty remain explicit. Review findings still retain exact engineering evidence for the implementer, while the user summary focuses on readiness and impact. The validated epic Kanban remains mandatory.

Manual instruction checks covered routine status, a consequential architecture decision, a failed acceptance check and a requested technical review. The rule changes support different levels of detail for those cases without removing risk disclosure or verification obligations. These are instruction inspections, not measured real-world communication outcomes.

Validation on the local working tree: the review-skill validator passed, `python scripts/check_skill_prompt_references.py` passed for 33 documents, and the five documentation guard modules listed in ONBOARDING §7 passed all 117 tests with `-q --no-cov`. Pytest emitted the existing environment warning for unrecognised `timeout`; no tests failed. `scripts/measure_process.py` measured 363 always-loaded lines against the unchanged ceiling of 380. No runtime code or dependencies changed. Delivery is local and uncommitted.
