---
description: The format of an epic's TRACKING.md under Tasks/epics/EPIC-nnn_slug/. Copy it, fill every brace, delete this front matter and instructional comments.
---

# EPIC-{nnn} — Tracking

<!-- Lightweight tracking index: high-level headings, Gantt schedule, and milestone log only. -->
<!-- DO NOT write implementation details, test outputs, or full specs here. Detailed problem context, design, acceptance criteria, and per-file notes belong strictly in each child task file under incomplete/ or completed/. -->
- **Epic:** {link to the parent epic README}
- **Status:** {🔵 Planned / 🟡 In Progress / ✅ Done (YYYY-MM-DD)}
- **Target Completion:** {YYYY-MM-DD}
- **Renders:** GitHub Markdown, VS Code Mermaid preview, or mermaid.live.

---

## 1. Schedule (Gantt)

<!-- Keep bars high-level (one per milestone/PR). Replace sample bars with your epic timeline. -->
```mermaid
gantt
    title EPIC-nnn - Epic Title
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m
    todayMarker stroke-width:2px,stroke:#d33,opacity:0.6

    section Spec
    Spec and sub-task breakdown           :done,    s1, 2026-09-01, 1d
    User review of spec                   :crit, done, s2, after s1, 1d

    section Phase 1 - Scaffolding
    PR 1.1 Contracts and unit tests       :active,  p11, after s2, 2d
    PR 1.2 Core service implementation    :         p12, after p11, 2d
    Phase 1 exit check                    :milestone, m1, after p12, 0d
```

---

## 2. Sub-tasks & PR Matrix

<!-- Keep rows to 1-line references. Clickable links point to active child task files under incomplete/ or completed/. -->

| Id | Sub-task | Branch / PR | Risk | Status | Target / Merged |
| :--- | :--- | :--- | :-: | :--- | :--- |
| {EPIC-nnnA} | {summary, linked to incomplete/ task file} | `{branch_name}` | {🟢 / 🟡 / 🔴} | {🔵 Planned / 🟡 Active / ✅ Merged} | {YYYY-MM-DD} |
| {EPIC-nnnB} | {summary, linked to incomplete/ task file} | `{branch_name}` | {🟢 / 🟡 / 🔴} | {🔵 Planned / 🟡 Active / ✅ Merged} | {YYYY-MM-DD} |

---

## 3. Milestone & Status Log

<!-- One line per event/PR. No long commentary or logs — summarize event and outcome in one sentence. Detailed notes belong in child task files. -->

| Date | Item | Event & Outcome |
| :--- | :--- | :--- |
| {YYYY-MM-DD} | Spec | Epic scaffolded, sub-tasks sliced, reviewed. |
| {YYYY-MM-DD} | PR 1.1 | Merged (PR #{number}) — {1-line outcome}. |

---

## 4. Blockers & Dependencies

| Blocker / Dependency | Impacted Tasks | Resolution / Owner | Status |
| :--- | :--- | :--- | :--- |
| {Prerequisite or external blocker} | {Task Ids} | {Resolution strategy or owner} | {🟡 Open / ✅ Resolved} |
