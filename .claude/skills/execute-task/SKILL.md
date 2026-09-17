---
name: execute-task
description: Implement or resume a requested task or epic sub-task in this repository, from acceptance criteria through verification and reporting. Use when asked to do a task, continue its implementation or finish an agreed change; not for review-only, proposal-only or status-only requests.
---

# Execute a task

Deliver the requested outcome with evidence. Use the existing task record and repository workflow; keep the process proportional to the change.

## 1. Establish the current state

Read `CLAUDE.md` and `.claude/ONBOARDING.md`, then `.claude/rules/task-execution-rule.md` and `.claude/rules/report-task-rule.md`. Check Git status and the diff before assuming unfinished work is untouched. Follow ONBOARDING §12 for a resumed task and §7 for authority; another repository has its own boundary.

Find the named task by ID or path. For an epic child, read the parent README, applicable decisions and dependencies. Compare its recorded status with the actual files, commits and tests. Reuse completed or partial work; do not create a duplicate task or replay changes already present. If a completed task receives new scope, record that as new work rather than silently rewriting its accepted outcome.

Before starting or resuming implementation of an epic task, show the whole epic's Mermaid Kanban in chat as required by `report-task-rule.md` §Epic overview before implementation. First validate the exact draft using [the Mermaid validation workflow](references/mermaid-validation.md); repair errors before displaying it. Mark the current task and explain the next step; refresh and revalidate changed boards when task state changes and at final handoff.

For a new implementation request, create the appropriate record under ONBOARDING §3 before editing implementation files. Bug records follow `.claude/rules/create-bug-report-rule.md`; repairs follow `.claude/rules/fix-bug-rule.md`. Do not add a duplicate BOT record merely to use this skill. A report-only request ends with the report and board update. An unaccepted proposal is not implementation approval. Questions, assessments and status requests do not require a new execution task.

## 2. Define the outcome and select the rules

Translate the request into observable acceptance criteria, scope and a verification method in the task file. Read the relevant SPEC and existing mechanism before choosing changes. For a small task, a short design paragraph is enough; an epic uses its existing phase plan. State the outcome and next step briefly to the user using the task-report rule.

Enumerate `.claude/rules/` recursively. Load unscoped rules and those whose paths or subject match the work; include relevant pitfalls. Use these routes where applicable:

| Work | Additional authority |
| :--- | :--- |
| Bug fix | `.claude/rules/fix-bug-rule.md` for repair/proof; `.claude/rules/create-bug-report-rule.md` for the report lifecycle. |
| EPIC-025 step | `.claude/skills/epic-025/SKILL.md`; retain its phase constraints and proof requirements. |
| Changed behavior or architecture | Affected SPEC/HLD/SDD and the architecture, domain, UI or async rules for the affected paths. |
| Verification | `.claude/rules/ci-rule.md` and `.claude/rules/testing-rule.md`; missing tools follow `.claude/rules/install-rule.md`. |
| Commits, PRs and delivery | `.claude/rules/commit-rule.md`, ONBOARDING §7 and `.claude/skills/pr-review/SKILL.md`. |

Check dependency readiness in the actual implementation. Resolve ordinary design choices within scope. Ask only for a missing decision that affects correctness/scope or an action requiring approval under the existing authority; include a recommendation. Continue independent work while that decision is pending.

## 3. Implement a verifiable step

Choose the next step that advances an acceptance criterion. Reuse the repository's existing contracts and patterns. Keep implementation, relevant tests and affected documentation together. Preserve unrelated changes and inspect the latest diff before modifying a file also being edited elsewhere.

Run focused checks while developing; use the required tier and existing coverage rather than inventing tests for documentation or assertions that merely repeat the implementation. If the work reveals a different root cause, update the bounded design and explain the consequence. Materially new scope becomes explicit follow-up work, not an invisible addition or omission.

Record important decisions and evidence in the task or existing ADR. Give progress updates when a result, risk or next step changes. When blocked, record the exact dependency, what can still proceed and what releases the block; do not treat missing evidence as success.

## 4. Verify the requested result

Map each acceptance criterion to observed evidence. Review the final diff for accidental changes and apply the relevant prompts from `pr-review`; an author's self-check is not the independent session required for a code merge.

Run the checks required by `ci-rule.md` for this change and delivery stage, including ONBOARDING §7's documentation-only exception when applicable. Record the commands, results, reviewed revision or working-tree snapshot and log paths. Read the actual log; any later relevant edit invalidates evidence for the prior snapshot. Diagnose failed checks without weakening tests, guards or baselines. Unrelated failures still prevent claiming the required gate passed.

If a required manual check cannot run, name the missing observation and keep that criterion unverified. Do not infer application behavior from a unit test or declare the task Done while required evidence is missing.

## 5. Close or leave a precise resumption point

Apply the completion contract in `task-execution-rule.md`. Update the task, affected SPEC/design and boards through ONBOARDING §6 or §12.3; regenerate counts instead of typing them. Bug closure uses its own rule. Include these final document changes in the applicable verification.

Carry out the requested delivery within ONBOARDING §7 authority. Inspect the index before any commit so unrelated work cannot ride along. When a code merge is part of the request, obtain the required independent review through the existing workflow; never substitute this session's self-check or merge your own code. If that review is unavailable, report the concrete remaining step.

If interrupted or awaiting a prerequisite, leave current evidence and the next executable action in the same task file, under the optional Resume section. Keep outstanding criteria unchecked; do not create a parallel handover document. Finish with the compact report from `report-task-rule.md`, including the actual verification and delivery state.
