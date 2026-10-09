# EPIC-037 — Tracking

- **Epic:** [README](README.md)
- **Status:** 🔵 Planned
- **Target Completion:** 2026-11-13 (four weeks from the start in the week of 2026-10-12; a target, not a commitment)
- **Renders:** GitHub Markdown, VS Code Mermaid preview, or mermaid.live.

---

## 1. Schedule (Gantt)

```mermaid
gantt
    title EPIC-037 - AI development leverage points
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m
    section Phase 0
    037A catalog                 :a, 2026-10-12, 2d
    037B metrics                 :b, 2026-10-12, 1d
    037F id issuer               :f, after b, 1d
    section Phase 1
    037C only-one guards         :c, after a, 4d
    037D sibling parity          :d, 2026-10-14, 4d
    section Phase 2
    037E demanding fake          :e, after d, 10d
    section Phase 3
    Review against baseline      :milestone, r, 2026-11-13, 0d
```

---

## 2. Sub-tasks & PR Matrix

| Id | Sub-task | Branch / PR | Risk | Status | Target / Merged |
| :--- | :--- | :--- | :-: | :--- | :--- |
| EPIC-037A | [capability catalog](incomplete/EPIC-037A_capability_catalog.md) | — | 🟢 | 🔵 Planned | 2026-10-14 |
| EPIC-037B | [system-health metrics](incomplete/EPIC-037B_system_health_metrics.md) | — | 🟢 | 🔵 Planned | 2026-10-13 |
| EPIC-037F | [one id issuer](incomplete/EPIC-037F_one_place_issues_task_ids.md) | — | 🟢 | 🔵 Planned | 2026-10-14 |
| EPIC-037C | [only-one guards](incomplete/EPIC-037C_only_one_guards.md) | — | 🟡 | 🔵 Planned | 2026-10-20 |
| EPIC-037D | [sibling parity tests](incomplete/EPIC-037D_sibling_parity_tests.md) | — | 🟡 | 🔵 Planned | 2026-10-20 |
| EPIC-037E | [demanding fake exchange](incomplete/EPIC-037E_demanding_fake_exchange.md) | — | 🔴 | 🔵 Planned | 2026-11-03 |

---

## 3. Milestone & Status Log

| Date | Item | Event & Outcome |
| :--- | :--- | :--- |
| 2026-10-09 | Spec | Epic scaffolded from the systems analysis; not started. |

---

## 4. Blockers & Dependencies

| Blocker / Dependency | Impacted Tasks | Resolution / Owner | Status |
| :--- | :--- | :--- | :--- |
| `hypothesis` as a test dependency | EPIC-037E | The owner approves or the task uses a hand-written seeded runner | 🟡 Open |
