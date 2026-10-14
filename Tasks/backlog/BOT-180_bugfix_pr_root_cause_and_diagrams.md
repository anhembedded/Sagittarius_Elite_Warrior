# BOT-180 — A fix pull request states its root cause, corrective action and before/after sequence

**Status:** 🟡 In progress
**Board:** A `fix:` pull request must carry Root cause, Corrective action and before/after Mermaid sequence diagrams on its own description, enforced by `scripts/check_fix_pr_body.py` in commit-lint.
**Source:** The owner, 2026-10-14: "nếu là PR fix bug thì phải có RC, CA, và mermaid sequence diagram, before vs after … mình cần cái comment trên PR á, chả bao giờ tui đọc bug report cả." (A bug-fix PR needs the root cause, the corrective action and a before/after Mermaid sequence diagram on the PR, because the owner reads PRs and never bug reports.)
**Risk:** 🟢 — a process rule and one CI step; it only fails a `fix:` PR whose description lacks the sections.
**Complexity:** S — one stdlib script, one workflow step, rule and template text.
**Depends on:** None

---

## 1. Context and problem
The fix's mechanism lived in the bug report, which the owner does not read. The PR description is the first thing GitHub shows and the owner's reading surface.

## 2. Acceptance criteria
- [ ] The description of every `fix:` PR carries `## Root cause`, `## Corrective action`, `## Sequence: before`, `## Sequence: after`.
- [ ] A Sequence section may hold `Not applicable: <reason>` only for a defect local to one function or one piece of text.
- [ ] `fix-bug-rule.md` §6.1 states both; `create-bug-report-rule.md` lets the report link to the PR.
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` has the four sections.
- [ ] CI fails a `fix` PR missing a heading, or a Sequence section with neither a `mermaid` `sequenceDiagram` block nor `Not applicable:`.
- [ ] The rubric has a check (E16) that the diagrams match the change.
- [ ] A well-formed `fix` body passes and each omission fails (tests).

## 3. Design
A small stdlib script reading `PR_TITLE` and `PR_BODY` from the environment (never the shell line), run as a step of the existing `commit-lint` job, which gains the `edited` event type so a description fix re-runs it. Mermaid syntax is not validated: GitHub renders the block and E16 judges truth.

## 3a. Reuse
`None: no UI or application need`; the guard follows `scripts/check_commit_messages.py` and is registered as gate step `fix pr body` in `scripts/rule_integrity/tags.py`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `scripts/check_fix_pr_body.py` | The guard. |
| `scripts/bot180_fix_pr_body_probe.py` | Probe driving the real script as CI does. |
| `tests/unit/scripts/test_check_fix_pr_body.py` | Pass and each-omission-fails tests. |
| `.github/workflows/commit-lint.yml` | The step, and the `edited` trigger. |
| `scripts/rule_integrity/tags.py` | Gate step `fix pr body`. |
| `.claude/rules/fix-bug-rule.md`, `create-bug-report-rule.md` | §6.1 and the link clause. |
| `.github/PULL_REQUEST_TEMPLATE.md` | The four sections. |
| rubric, `SKILL.md`, `reviewer.md`, `ONBOARDING.md` | Check E16; ID count 109 → 110. |

## 5. Testing
Unit tier: `tests/unit/scripts/test_check_fix_pr_body.py`; the probe; commit tier; `python3 scripts/check_skill_prompt_references.py`.

## 6. Docs touched
`.claude/` rule, template and rubric files listed above; no `Docs/` change, because no product behaviour moves.
