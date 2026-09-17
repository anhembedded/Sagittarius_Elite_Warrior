---
description: The task execution contract — bounded scope, observable acceptance, resumable evidence and honest completion; workflow in execute-task.
paths:
  - "Tasks/**/*.md"
  - ".claude/templates/task.md"
---

# Task execution

Applies when implementing or resuming a task or epic child. ONBOARDING §3/§6/§12 owns record locations and bookkeeping; §7 owns authority. Bug repairs use `fix-bug-rule.md`; their records use `create-bug-report-rule.md`. The workflow is `.claude/skills/execute-task/SKILL.md`; this file defines its completion contract.

## Outcome and scope

- Before implementation, the record identifies the requested outcome, observable acceptance criteria, dependencies and how each criterion will be checked. Use `.claude/templates/task.md`; keep the design proportional to the change. `[eye]`
- Read the real diff before resuming. Preserve work already present; a stale status is not permission to overwrite files. Keep material scope changes and deferrals explicit, with a reason and follow-up when needed. Do not silently drop an agreed criterion or convert an unaccepted proposal into implementation. `[review: A1, A6]`
- Continue decisions and work already authorised under ONBOARDING §7. Request only genuinely missing decisions or required approvals; a routine design choice is not a reason to stop. `[eye]`

## Evidence and completion

- A checked acceptance item points to evidence for that outcome: test or manual result, relevant revision/snapshot, and command/log or artifact where applicable. Distinguish passed, failed, not run and not applicable with a reason. Test counts alone do not prove acceptance. `[review: E1, E2, B6]`
- Mark Done only when all agreed criteria, required verification and requested delivery are complete, and the task and affected documents/boards reflect them. CI requirements remain in `ci-rule.md`; a self-review never replaces ONBOARDING §7's independent code-merge review. `[review: B6, K1, K4]`
- Implementation, verification, review and delivery are separate facts. A local edit is not a commit, a pushed branch is not a merge, and a passing gate is not a manual observation. Delivery beyond the user's requested outcome is not an extra completion requirement. `[eye]`

## Unfinished work

- Keep blocked or partly verified work open in its current pool. Record the blocker, affected criterion, evidence already obtained and next executable action in the task's Resume section. A blocked task remains In progress with a stated blocker; do not invent a separate board or status pool. `[eye]`
- On resumption, recheck the repository and outstanding criteria. Reuse evidence only if it still covers the relevant snapshot; do not rerun unchanged checks without a reason or claim old evidence proves new edits. Report through `report-task-rule.md`. `[eye]`
