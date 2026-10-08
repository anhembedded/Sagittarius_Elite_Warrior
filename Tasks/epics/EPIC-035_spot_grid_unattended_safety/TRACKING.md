# EPIC-035 — Tracking

- **Epic:** [EPIC-035](README.md)
- **Status:** 🔵 Planned
- **Target Completion:** Phase 1 first; no date set by the owner
- **Renders:** GitHub Markdown, VS Code Mermaid preview, or mermaid.live.

---

## 1. Schedule (Gantt)

```mermaid
gantt
    title EPIC-035 - Spot Grid supervision
    dateFormat  YYYY-MM-DD
    axisFormat  %d/%m
    todayMarker stroke-width:2px,stroke:#d33,opacity:0.6

    section Spec
    Audit, epic and tasks written        :done, s1, 2026-10-08, 1d

    section Phase 1 - Supervision
    035A Price subscription and staleness :p1a, after s1, 5d
    035B User-data stream heals           :p1b, after s1, 5d
    035C No unmanaged orders              :p1c, after s1, 5d
    Phase 1 exit check                    :milestone, m1, after p1c, 0d

    section Phase 2 - Resilience
    035D to 035J                          :p2, after m1, 15d

    section Phase 3 - Alerting
    035K to 035O, 035W, 035X (W, X not yet) :p3, after p2, 10d

    section Phase 4 - Accuracy
    035P to 035V                          :p4, after p3, 10d
```

---

## 2. Sub-tasks & PR Matrix

| Id | Sub-task | Branch / PR | Risk | Status | Target / Merged |
| :--- | :--- | :--- | :-: | :--- | :--- |
| EPIC-035A | [Price subscription](completed/EPIC-035A_the_bot_owns_its_price_subscription.md) | `epic-035a-bot-owns-price-subscription`, PR #430 | 🔴 | ✅ Done (2026-10-08) | merged |
| EPIC-035B | [User-data stream](completed/EPIC-035B_the_user_data_stream_heals_itself_and_catches_up.md) | branch `claude/epic-035b-user-stream-heals`, PR #431 | 🔴 | ✅ Done (2026-10-08) | pull request open, awaiting merge |
| EPIC-035C | [Unmanaged orders, stuck states](completed/EPIC-035C_no_unmanaged_orders_and_no_stuck_states.md) | branch `epic-035c-no-unmanaged-orders` | 🔴 | ✅ Done (2026-10-08) | pull request open, awaiting review |
| EPIC-035J | [Reference price has an age](completed/EPIC-035J_the_reference_price_has_an_age.md) | branch `claude/epic-035d-035j-resilience` | 🟡 | ✅ Done (2026-10-08) | pull request open, awaiting review |
| EPIC-035D | [Retry and backoff](completed/EPIC-035D_retry_and_backoff_for_exchange_calls.md) | branch `claude/epic-035d-035j-resilience` | 🟡 | ✅ Done (2026-10-08) | pull request open, awaiting review |
| EPIC-035E–I | Phase 2 (see the [README](README.md) §3) | — | 🟡 | 🔵 Planned | — |
| EPIC-035K–O | Phase 3 (see the [README](README.md) §3) | — | 🟡 | 🔵 Planned | — |
| EPIC-035W | [Health visible on screen](incomplete/EPIC-035W_the_bots_health_is_visible_on_screen.md) | — | 🟡 | 🔵 Planned; owner: not yet | — |
| EPIC-035X | [Decision audit trail](incomplete/EPIC-035X_every_bot_decision_is_in_an_audit_trail.md) | — | 🟡 | 🔵 Planned; owner: not yet | — |
| EPIC-035P–V | Phase 4 (see the [README](README.md) §3) | — | 🟡 | 🔵 Planned | — |

---

## 3. Milestone & Status Log

| Date | Item | Event & Outcome |
| :--- | :--- | :--- |
| 2026-10-08 | Spec | Epic scaffolded from the audit; owner decisions D1–D4 recorded (D4: option (a)). |
| 2026-10-08 | 035W, 035X | Added to Phase 3 at the owner's request; the owner asked that they not be started yet (D5). |
| 2026-10-08 | 035A | Implemented; PR #430 merged. |
| 2026-10-08 | 035Q | `BUG-188` delivered the reconciler's executed-quantity read for *saved* orders; adopted orders still start at zero, so 035Q stays open. |

---

## 4. Blockers & Dependencies

| Blocker / Dependency | Impacted Tasks | Resolution / Owner | Status |
| :--- | :--- | :--- | :--- |
| D4: Start with the price outside the range | EPIC-035L | Decided 2026-10-08, option (a); recorded in the decision file | ✅ Resolved |
