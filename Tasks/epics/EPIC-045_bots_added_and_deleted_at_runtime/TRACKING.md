# EPIC-045 — Tracking

- **Epic:** [README](README.md)
- **Status:** 🟡 In Progress
- **Target Completion:** 2026-10-28

---

## 1. Schedule (Gantt)

```mermaid
gantt
    title EPIC-045 - add and delete a bot on the running host
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m
    todayMarker stroke-width:2px,stroke:#d33,opacity:0.6

    section Decision
    Owner decision and epic scaffold      :done,    s1, 2026-10-21, 1d

    section Phase 1 - A, B, E
    PR 1 bot add, bot delete, runbook     :active,  p1, after s1, 2d

    section Phase 2 - D
    PR 2 the parity guard                 :         p2, after p1, 1d

    section Phase 3 - C
    PR 3 bot apply beside a host          :         p3, after p2, 3d
```

---

## 2. Sub-tasks & PR Matrix

| Id | Sub-task | Branch / PR | Risk | Status | Target / Merged |
| :--- | :--- | :--- | :-: | :--- | :--- |
| EPIC-045A | `bot add` | `claude/epic-045-runtime-bot-add-delete` | 🟡 | 🟡 Active | 2026-10-23 |
| EPIC-045B | `bot delete` | `claude/epic-045-runtime-bot-add-delete` | 🟡 | 🟡 Active | 2026-10-23 |
| EPIC-045E | Runbook | `claude/epic-045-runtime-bot-add-delete` | 🟢 | 🟡 Active | 2026-10-23 |
| EPIC-045D | Parity guard | not started | 🟢 | 🔵 Planned | 2026-10-24 |
| EPIC-045C | `bot apply` beside a host | not started | 🔴 | 🔵 Planned | 2026-10-28 |

---

## 3. Milestone & Status Log

| Date | Item | Event & Outcome |
| :--- | :--- | :--- |
| 2026-10-21 | Spec | Epic scaffolded; decision record written; A, B, E begun. |

---

## 4. Blockers & Dependencies

| Blocker / Dependency | Impacted Tasks | Resolution / Owner | Status |
| :--- | :--- | :--- | :--- |
| Delete's exposure rule is stricter than the tab's (D4) | B | the owner may veto in the PR | 🟡 Open |
