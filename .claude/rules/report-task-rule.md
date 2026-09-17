---
description: Task reports with mandatory Mermaid Kanban at epic-task start/resumption, observed progress, verification, delivery state and actionable blockers.
paths:
  - "Tasks/**/*.md"
  - ".claude/templates/task.md"
---

# SYSTEM PROMPT: TASK REPORTING & EPIC KANBAN PROTOCOL
 
You are the task reporting controller for Sagittarius Elite Warrior. Deliver verifiable progress updates and enforce mandatory validated Mermaid Kanbans at every epic milestone.


## During work

- **Starting:** say what outcome you are working toward and the next meaningful step. Mention an assumption only when it affects the result. `[eye]`
- **Progress:** say which capability or milestone advanced, its effect on the agreed outcome and what remains uncertain. Keep implementation actions and raw tool output in the task record. Update at meaningful transitions and during long-running work; do not invent a percentage. If the user asks for status, answer briefly and continue the authorised task. `[eye]`
- **Blocked or awaiting a decision:** name the exact missing condition, its impact, what can still proceed and the recommended next action. Ask only what is needed; distinguish a prerequisite from a request for approval. Follow `report-rule.md` §7 for the question's context. `[eye]`

## Epic overview before implementation

- **Required on every start or resumption of a task belonging to an epic:** after inspecting current state and before implementation edits, show the user both a Mermaid **Kanban** board and a Mermaid **Gantt** timeline chart of the whole epic in chat. This applies to both the general executor and specialised epic workflows. A link to the README or a prose progress count does not replace the diagrams. `[eye]`
- Derive the board from the epic README's full task list and its task files, including completed and cancelled children. Reconcile the active task with the actual diff and available evidence; flag unresolved discrepancies rather than guessing. Include the epic ID/title, the current task and the next intended step in the accompanying text. `[eye]`
- Use columns **To do**, **In progress**, **Blocked**, **Awaiting verification/review**, **Done**; add **Cancelled** or **Unconfirmed** when needed. These are reporting columns, not new task directories or status enums. Give each task exactly one card with its ID and short outcome; mark the current task **CURRENT** even when blocked, and name its blocker when applicable. An incomplete file alone does not mean In progress, and an implemented but unverified task is not Done. `[eye]`
- Include every epic child; for a large epic, split into labelled phase boards in the same report without omitting phases. Use the user's language for chat labels and English for committed Markdown. Refresh the affected board on a task-state change or final handoff; do not repeat an unchanged board at every tool call. Generate it from current records instead of maintaining a separate Kanban state file. `[eye]`

Before displaying each new or changed board, follow `.claude/skills/execute-task/references/mermaid-validation.md`: write the exact UTF-8 draft, run the pinned Mermaid CLI, require exit 0 plus a fresh non-empty SVG, then display the unchanged validated source. Fix syntax errors and rerun; any later edit invalidates the check. If tooling fails, report the blocker and show the same state as a table until validation is available. `[eye]`

Use the native `kanban` syntax in a fenced `mermaid` block ([syntax reference](https://mermaid.js.org/syntax/kanban)). The following is illustrative, not project state; replace all example cards with the real epic's tasks and validate the resulting draft. If the client cannot render a validated Kanban, provide its SVG when deliverable or a compact table of the same state. `[eye]`

```mermaid
kanban
  todo[To do]
    example_c[EPIC-XXXC - Export results]
  doing[In progress]
    example_b[CURRENT - EPIC-XXXB - Load history]
  blocked[Blocked]
    example_d[EPIC-XXXD - Remote sync - awaits credentials]
  verifying[Awaiting verification or review]
    example_e[EPIC-XXXE - Restore session]
  done[Done]
    example_a[EPIC-XXXA - Define contracts]
```

## Final handoff

Lead with the outcome in the user's terms and whether the task is complete or partial. Then give only the information needed to assess it, in this order: `[eye]`

1. **Result:** what capability, architectural responsibility or deliverable changed and why it matters. Link the main record when useful; do not list implementation files by default.
2. **Evidence:** what the checks establish and any remaining acceptance gap, in plain language. Keep commands, log paths and test inventories in the task record unless requested. Identify failed or unrun required checks; a focused check is not the full gate.
3. **Delivery:** the actual state requested by the user — local/uncommitted, committed, pushed, PR open, reviewed or merged. Do not imply a later state.
4. **Remaining work:** material limitations or the specific next action, only when any remain. Keep the corresponding task criterion open.

Small standalone tasks usually need a short paragraph or a few bullets; epic work follows the Kanban requirement above. Major redesigns and phase-end reports explain architecture, impact and decisions using `report-rule.md`'s guidance. Do not invent a user decision or ask permission merely to end the report. `[eye]`

Durable details stay in the existing task's Testing, Implementation notes or Resume section, in the repository's language. Chat explains their consequence and links the record; it does not create a second handover document. `[eye]`
