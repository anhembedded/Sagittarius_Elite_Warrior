# EPIC-048 — The UI reaches the application only through the command dispatcher and bus events

- **Status:** 🔵 Planned
- **Repositories:** Elite
- **Origin:** [EPIC-047](../EPIC-047_vps_bots_tab/README.md)'s Discover Finding E (the UI reaches the application around the dispatcher and the bus), accepted by the owner on 2026-10-24, and charter decision G9 (a separate epic, done first), settled on the owner's delegation: *"các quyết định, bạn thay tôi quyết định phù hợp tất cả hiến pháp"* ("decide them for me, consistent with the whole Constitution"). De-risk R7 measured the debt.
- **North star:** [`Docs/HLD/11_desktop_workbench.md`](../../../Docs/HLD/11_desktop_workbench.md) and [`.claude/rules/architecture-rule.md`](../../../.claude/rules/architecture-rule.md); the rule's new text is child A's work.
- **Decisions:** [`DECISION_2026-10-24_the_ui_reaches_the_application_through_its_doors.md`](DECISION_2026-10-24_the_ui_reaches_the_application_through_its_doors.md) — the rule, the allowlist, the guard and its baseline, where computation goes, the gateway, the order of work (G9).
- **Dependencies:** None. **[EPIC-047](../EPIC-047_vps_bots_tab/README.md) depends on this epic's children A and B.**

---

## 1. Decisions already made
1. The UI reaches the application through the dispatcher and the bus, plus a UI-only allowlist and three pure-code ports (ADR D1, D2).
2. A guard test holds it with R7's method and a baseline that only falls (ADR D3, D4).
3. The pure assessment moves to the application layer and still runs on the desktop; two new queries carry the host facts (ADR D5).
4. Presenters receive a narrow gateway, not the container (ADR D6).
5. EPIC-047's code starts once 048A and 048B are done; 048C and 048D may finish later (ADR D7).

## 2. Goals — measurable
| Metric | Today (measured 2026-10-24, `5ddbd68`, De-risk R7) | When the epic is done |
| :--- | :-: | :-: |
| UI imports around the doors (`src/modules/*/ui/`, R7's method) | 215 in 82 files over 18 screen areas | 0 `fn`, port and adapter imports; `data` imports at a baseline that only fell. Child A writes the first guard count: 197 expected once `IBotKind`, `IBotKindCatalog` and `ICandleFeed` are allowed |
| Functions under `ui/` that take the whole `IContainer` | 30 | 0 |
| Imports in `bots/ui/bots_screen` | 45 (24 application-service, 17 port, 2 other, the plan-file adapter) | 0 outside the allowlist, so EPIC-047 can start |
| Reads the Bots screen runs on the UI thread | 1 query (`ExportBotPlanQuery`) and 4 non-query reads (DERISK §8.1) | 0 |
| A guard that fails on a new bypass | none | one, in `tests/unit/architecture/` |

## 3. Sub-tasks, ordered by risk
| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-048A](incomplete/EPIC-048A_the_doors_rule_and_its_guard.md) | The rule in `architecture-rule.md` and the guard test with R7's method, the count as a baseline that only shrinks, and the allowlist with `IBotKind`, `IBotKindCatalog` and `ICandleFeed` | Elite | None | 🟡 | Planned |
| [EPIC-048B](incomplete/EPIC-048B_the_bots_screen_through_the_doors.md) | The Bots screen through the doors: `GetBotRunFactsQuery` and `GetVenueChoicesQuery`, the pure assessment moved into the application layer and still run on the desktop, the reads off the UI thread | Elite | 048A | 🔴 | Planned |
| [EPIC-048C](incomplete/EPIC-048C_presenters_receive_a_narrow_gateway.md) | Presenters receive a narrow application gateway instead of the whole container | Elite | 048A | 🟡 | Planned |
| [EPIC-048D](incomplete/EPIC-048D_the_other_screens_cut_down_to_the_baseline.md) | The other screens cut down against the baseline (split per screen when started) | Elite | 048A, 048C | 🟡 | Planned |

## 4. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 1 — the mechanism (048A) | The rule is in `architecture-rule.md`; the guard runs in the full gate with a baseline; adding a bypass import fails it | The guard's mutation check (a planted import fails it); the PR's `ci-local.ps1 -Full` log. Not run |
| 2 — the Bots screen (048B) | `bots/ui/bots_screen` has no import outside the allowlist; the screen renders as before; the host-fact reads of DERISK §8.1 are off the UI thread | The guard's per-area count for the Bots screen reads 0; the Bots screen's existing tests unchanged and green; a frame comparison before and after. Not run |
| 3 — the gateway (048C) | No function under `ui/` takes `IContainer` | The guard's container count reads 0. Not run |
| 4 — the other screens (048D) | Every area at its target count | The guard's baseline file shows each area's count fell. Not run |

EPIC-047 may start after phase 2.

## 5. Out of scope
- The remote link, the bridge and the VPS tab: [EPIC-047](../EPIC-047_vps_bots_tab/README.md).
- Any change to what a screen shows or a bot decides: the epic moves reads and a pure function, and every child proves "no visible change".
- Forbidding `data` imports at once (ADR D4): they get a second baseline line, cleared last.
- Any Engine file, setting or dependency.

## Notes (newest first)
- **2026-10-24** — Epic scaffolded with the decision record (G9) and four children, after De-risk R7 measured the debt (215 imports, 30 container-taking functions); EPIC-047 is gated on 048A and 048B.
