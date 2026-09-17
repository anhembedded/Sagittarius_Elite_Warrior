# BOT-138 — Execute tasks with explicit outcomes and concise reports

**Status:** ✅ Done (2026-09-17)
**Source:** User, 2026-09-17: "Viết cho tôi 1 cái skill làm task, và các rule đi chung, report-task-rule. v.v... bạn chứ đề xuất thoải mái" ("Write a skill for executing tasks and accompanying rules, including report-task-rule; feel free to propose the design").
**Risk:** 🟢 — Instructions, templates and navigation only.
**Complexity:** S — Compose existing workflows and add the missing task contract.
**Depends on:** None.

## 1. Context and problem
Task formats and specialised workflows exist, but there is no general execution skill. Acceptance, resumption and partial completion need consistent handling. Routine task updates should expose outcomes and verification without the full milestone-report ceremony.

## 2. Acceptance criteria
- [x] Provide one executable task workflow covering new work, resumption, verification and completion.
- [x] Keep task execution and task reporting rules scoped and distinct from existing CI, bug, commit and review authorities.
- [x] Distinguish local implementation, verified outcomes and delivery state; keep blocked or unverified work open.
- [x] Support short progress/final reports and link the workflow from navigation and the task template.
- [x] Pass skill validation, reference checks and existing documentation guards without increasing any guard ceiling.
- [x] Follow-up: show a Mermaid Kanban of the whole epic before starting or resuming any child task, mark the current task, and refresh on state changes and final handoff.
- [x] Follow-up: validate each new or changed Mermaid draft before display, with successful and deliberately failing CLI examples proving the check.

## 3. Design
Add `execute-task` with two path-scoped rules. Keep the task file as the durable record and ONBOARDING as the lifecycle/authority map. The existing reporting rule retains language and major milestone presentation; the task-report rule defines the compact form for routine execution. Reuse the bug and epic-specific workflows when applicable.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/skills/execute-task/SKILL.md` | General execution workflow and routes to specialised rules. |
| `.claude/skills/execute-task/references/mermaid-validation.md` | Executable official CLI workflow; success evidence, immutable checked source and failure fallback. |
| `.claude/rules/task-execution-rule.md` | Scope, acceptance, evidence and completion contract. |
| `.claude/rules/report-task-rule.md` | Progress, blocker and final task-report content. |
| `.claude/rules/report-rule.md` | Route routine task reports to their compact form. |
| `.claude/templates/task.md` | Optional interruption record and evidence/delivery notes. |
| `.claude/templates/epic.md` | Identify the sub-task table as the source for the required Kanban report. |
| `.claude/skills/epic-025/SKILL.md` | Apply the Kanban requirement even when invoked directly. |
| `CLAUDE.md` | Task execution and reporting entry points. |
| `.claude/ONBOARDING.md` | Announce the scoped rules and general workflow. |
| `.claude/README.md` | Invocation examples and regenerated inventory. |
| `Tasks/ROADMAP.md` | Task record and regenerated counts. |

## 5. Testing
Run skill-creator's validator, the reference checker and ONBOARDING §7's documentation guards. Walk the instructions against a small document change, a bug, resumed dirty work, a missing acceptance decision, failed verification and a requested code merge. These scenario inspections validate instruction consistency, not observed agent performance.

## Implementation notes

Follow-up, 2026-09-17: the user requires a Mermaid Kanban before starting a task inside an epic, so the report rule now makes this mandatory on start/resumption for both executors. It covers every epic child, marks CURRENT, derives state from existing records and evidence, and refreshes on state changes/final handoff. Reporting columns do not create new lifecycle states or directories. The English sample is illustrative, not live project state. The later validation follow-up below now requires actual CLI execution, not only reading the syntax documentation.

The user then requested the validate-before-display flow. Both executors and the shared reporting rule now route to the official CLI workflow: save exact UTF-8 source, render, require exit 0 plus a fresh non-empty SVG, and display unchanged source. Syntax errors require repair and revalidation; environment failures use an explicitly unverified table fallback. A successful render does not prove support in the user's chat client.

Real CLI checks used `@mermaid-js/mermaid-cli@11.17.0`, Node v24.19.0 and installed Chrome through a temporary Puppeteer config. The CLI was installed in npm's cache with browser download skipped; no application dependency or configuration changed. Temporary input/output/log files were written under `C:/Users/hoang/AppData/Local/Temp/sew-mermaid-validation-3z2u7lth`.

| CLI input | Expected | Observed |
| :--- | :--- | :--- |
| Rule's Kanban sample | Exit 0, fresh SVG | Exit 0, non-empty SVG |
| Kanban with Vietnamese labels | Exit 0, fresh SVG | Exit 0, non-empty SVG |
| Flowchart | Exit 0, fresh SVG | Exit 0, non-empty SVG |
| Kanban with an unclosed label | Nonzero exit | Exit 1, parse error, no SVG |

The checked rule sample's SHA-256 is `87D30191BD9390ABDC54CA0A2D26CBADC96D8594D2C7F43E09C48340AC86368D`; the deliberately invalid input is `11433637B57F0939D7E1D727CE2C1AE002D8C949A6B40D7E121C13441FDC4DBA`. These checks exercise the real Mermaid parser/rendering path. This is an instructed pre-display check, not a chat interception hook that mechanically prevents an agent from skipping it.

The requested artifacts are available locally: the `execute-task` skill, task execution and reporting rules, updated navigation and task template. No commit, push or merge was requested or performed. Existing CI, bug-fix, commit and independent-review authorities remain in their owning files.

| Acceptance | Evidence |
| :--- | :--- |
| Complete workflow | `.claude/skills/execute-task/SKILL.md` covers discovery, acceptance, implementation, verification and closure/resumption. |
| Scoped rules | Both new rules declare task-document/template paths; the navigation and manifest guards passed. |
| Honest completion | `task-execution-rule.md` separates verified outcomes from requested delivery and keeps missing criteria open. |
| Reporting and resumption | `report-task-rule.md` defines compact updates/handoff; `report-rule.md` routes routine tasks there; the task template has an optional Resume section. |
| Validation | Skill metadata validator and reference checker passed; all 117 required document-guard tests passed. `git diff --check` passed. |

Manual instruction walkthroughs (not independent agent executions):

| Scenario | Route and result |
| :--- | :--- |
| Small documentation change | Task acceptance and document-only checks; compact final report; no runtime tests invented. |
| Reported bug | Existing bug report and fix-bug rule; regression evidence before the fix; no duplicate BOT record. |
| Resume with existing edits | Read status/diff, compare actual work to the task and preserve edits; reuse evidence only for the covered snapshot. |
| Missing acceptance decision | Ask for the missing decision with context; continue independent work and keep the affected criterion open. |
| Required check fails | Diagnose without weakening the check; leave the task open with evidence and the next executable action. |
| Requested code merge | Independent session required under ONBOARDING §7; author self-review does not grant merge authority. |

Checks ran on the local working tree based on `540587ea`. Commands: `python scripts/check_skill_prompt_references.py`, the skill-creator `quick_validate.py` against the new skill, and the five pytest document-guard modules listed in ONBOARDING §7 with `-q --no-cov`. The checker resolved references across 32 documents. Pytest emitted one environment warning for the unrecognised `timeout` option; there were no test failures. `python scripts/measure_process.py` measured 373 always-loaded lines against the unchanged ceiling of 380. These checks establish document wiring and consistency, not real-world agent execution quality.
