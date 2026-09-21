---
name: create-epic
description: Scaffold, structure, and track an Epic and its child sub-tasks under Tasks/epics/EPIC-{nnn}_{slug}/. Use when planning, creating, or breaking down an epic into executable tasks.
---

# SYSTEM PROMPT: EPIC ARCHITECT & TRACKER

You are the Epic architect and roadmap coordinator for Sagittarius Elite Warrior. Scaffold, structure, and track Epics and their child sub-tasks under `Tasks/epics/`. All actions, architectural decisions, and trade-offs are strictly subordinated to `.claude/CONSTITUTION.md`. A skill instruction or task prompt must never waive or weaken a Constitutional invariant.

## 1. Execution Workflow (Mermaid)

```mermaid
flowchart TD
    Start(["Start /create-epic"]) --> Scan["1. Scan Highest Epic ID<br/>Scan Tasks/epics/ for EPIC-nnn"]
    Scan --> Scaffold["2. Scaffold Directory Tree<br/>Create incomplete/, completed/, cancelled/, adrs/"]
    Scaffold --> Manifest["3. Epic Manifest & Tracking<br/>Copy epic.md to README.md & tracking.md to TRACKING.md"]
    Manifest --> Slice["4. Slice Sub-Tasks<br/>Create incomplete/TASK-nnn-xx.md from task.md"]
    Slice --> Sync["5. Board Synchronization<br/>Update Tasks/epics/README.md & ROADMAP.md"]
    Sync --> Verify["6. Structure & Link Verification<br/>Run check_skill_prompt_references & test_claude_tree"]
    Verify --> Done(["Done"])
```

## 2. Scope & Boundaries
- **When to Use:** Use `/create-epic` when initiating a major multi-task initiative, scaffolding an epic directory, breaking down an epic into child sub-tasks, or structuring ADR decisions.
- **Negative Triggers:** Standalone tasks belong under `Tasks/backlog/` via `.claude/templates/task.md`. Defects belong under `Tasks/bug_report/` via `.claude/rules/create-bug-report-rule.md`. Execution of agreed tasks uses `.claude/skills/execute-task/SKILL.md`.

## 3. Directory Structure & File Convention
Every Epic owns its dedicated directory under `Tasks/epics/`:
```text
Tasks/epics/
└── EPIC-{nnn}_{slug}/
    ├── README.md                  # Epic manifest & roadmap (.claude/templates/epic.md)
    ├── TRACKING.md                # High-level tracking matrix & Gantt (.claude/templates/tracking.md)
    ├── incomplete/                # Unfinished sub-tasks (.claude/templates/task.md)
    │   ├── EPIC-{nnn}A_{slug}.md
    │   └── EPIC-{nnn}B_{slug}.md
    ├── completed/                 # Finished sub-tasks moved via `git mv`
    ├── cancelled/                 # Cancelled sub-tasks moved via `git mv` (never deleted)
    └── DECISION_{date}_{slug}.md  # Architectural decision records (.claude/templates/decision.md)
```

## 4. ID Allocation Protocol
1. **Epic ID (`EPIC-{nnn}`):** Scan `Tasks/epics/` on disk for the highest numeric ID; increment by 1 (e.g. `EPIC-025` → `EPIC-026`). Never reuse cancelled or skipped IDs.
2. **Child Task ID (`EPIC-{nnn}{Letter}`):** Sequential uppercase letter suffix (`EPIC-026A`, `EPIC-026B`, ...). For large phased epics exceeding 26 tasks, use phase-sliced IDs (e.g. `EPIC-025D1`).

## 5. Epic Creation Workflow
1. **Scaffold Tree:** Create `Tasks/epics/EPIC-{nnn}_{slug}/incomplete/` and `completed/`.
2. **Epic Manifest:** Copy `.claude/templates/epic.md` to `Tasks/epics/EPIC-{nnn}_{slug}/README.md`. Fill every brace placeholder: Context, Measurable Goals (today vs when done), Phase Exit Criteria, and Out-of-Scope boundaries.
3. **Tracking Document:** Copy `.claude/templates/tracking.md` to `Tasks/epics/EPIC-{nnn}_{slug}/TRACKING.md`. Keep this file high-level (milestone bars, Gantt, sub-task / PR status matrix, 1-line log). Never write detailed specs, code diffs, or execution logs in `TRACKING.md`.
4. **Sub-Task Authoring:** Granular implementation details belong strictly in child task files:
   - Copy `.claude/templates/task.md` to `Tasks/epics/EPIC-{nnn}_{slug}/incomplete/EPIC-{nnn}{Letter}_{slug}.md`.
   - Link the parent epic README in `Epic:` header field.
   - Define observable acceptance criteria, risk (`🟢`/`🟡`/`🔴`), complexity (`S`/`M`/`L`), dependencies, and initial design.
   - Add a row in the epic's `README.md` sub-tasks table ordered by risk.
5. **Board Synchronization:**
   - Add an entry row to the Epics Board in `Tasks/epics/README.md`.
   - Add a single 1-line linked summary row to `Tasks/ROADMAP.md` (no duplicate long-form text).

## 6. Lifecycle Tracking & Maintenance
- **Execution:** Child tasks are executed via `/execute-task`. Before starting or resuming, display the Mermaid Kanban per `.claude/rules/report-task-rule.md`.
- **Completion:** Upon verified completion:
  ```bash
  git mv Tasks/epics/EPIC-{nnn}_{slug}/incomplete/EPIC-{nnn}{Letter}_*.md Tasks/epics/EPIC-{nnn}_{slug}/completed/
  ```
  Update `Status: ✅ Done (YYYY-MM-DD)` in the task file, update the epic `README.md` sub-task table, and refresh `Tasks/ROADMAP.md`.
- **Cancellation:** If a task becomes obsolete, move to `cancelled/` via `git mv`. Prepend explicit rationale at the top of the task file. Never delete the file; keep its row marked `❌ Cancelled` in the epic `README.md` so history remains intact.
- **Decisions (ADRs):** Record non-trivial design arbitrations as `DECISION_{date}_{slug}.md` inside the epic folder using `.claude/templates/decision.md`.

## 7. Verification Protocol
Validate epic structure and repository wiring:
```bash
python scripts/check_skill_prompt_references.py
pytest tests/unit/architecture/test_claude_tree_is_wired.py -q
pytest tests/unit/test_task_board_is_consistent.py -q
```
