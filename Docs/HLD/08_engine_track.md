# §8 — The Engine track: what the Engine gets, when, and by what criterion

- **Status:** 🔵 Proposed 2026-09-13, in answer to the user: *"plan sao tui chưa thấy nói tới sẽ làm
  gì với engine nhỉ?"* ("why does the plan not say what will be done with the Engine?"). §5 gave the
  *split*; this section gives the *plan*: the order of work on the Engine side, and the rule that
  decides when a piece of code moves from the application into the Engine.
- **Diagrams:** [`diagrams/hld-04a_engine_track_zones.puml`](diagrams/hld-04a_engine_track_zones.puml)
  — the high view: three zones, one direction of travel, and the lift criterion (§8.1–8.3);
  [`diagrams/hld-04b_engine_track_schedule.puml`](diagrams/hld-04b_engine_track_schedule.puml)
  — the detail: every piece, where it is built, where it lifts, and at which step E0–E3 (§8.4).

## 8.1 The pattern: a harvested framework, not a designed-first one

The Engine is the user's reusable core (ADR D10), so every mechanism this redesign needs *will*
end up there. The question is only **when**. Two orders were considered:

| Order | What happens | Why not |
| :--- | :--- | :--- |
| **Engine first** — design `NavigationService`, the contribution registry and the region runtime in the Engine, then make the app consume them | The abstractions are chosen with the *least* information. The Engine's own `EPIC-001D` says exactly this about itself: *"Choosing these abstractions early means choosing them with the least information, and a wrong abstraction with live consumers is far more expensive to correct than duplicated code."* | — |
| **Harvest** — build the mechanism inside the app, shaped as if it were Engine code (no app import, Engine package layout), prove it on two surfaces and two modules, then **lift** it into the Engine | The Engine receives an API that a real application has already exercised. This is Fowler's *Harvested Framework* (2003) and the way Rails was extracted from Basecamp. It costs one move and one import rewrite per lifted piece. | chosen |

"Apply before you invent" (`ONBOARDING.md` §7) applies to the order of work as much as to the
code: harvesting is the named pattern for growing a framework out of an application.

## 8.2 What is lift-ready from day one — the rule that makes harvesting cheap

Everything that will move to the Engine is written in the app under `core/contracts/` and
`shell/workbench/`, and obeys three constraints from Phase 0, enforced by the guards in §6.1:

1. **No import from `modules/`, `support/` or the rest of `shell/`.** It may import only the Engine
   and the standard library. (`core/` already has this guard.)
2. **Engine package layout.** `core/contracts/contribution.py` is written as the future
   `sagittarius_engine/extensions/workbench/contribution.py`; the lift is `git mv` plus an import
   rewrite, never a redesign.
3. **The app never subclasses what it will lift except through the intended seam** — a module
   subclasses `BoundedContextModule`; nothing else in the app touches its internals.

## 8.3 The lift criterion — all three, checked, written into the lifting task

A piece moves from the app to the Engine when:

1. the guard confirms it imports nothing application-specific (§8.2 rule 1);
2. it is used by **at least two surfaces or two modules** of this application — one consumer is
   not evidence that the API is general (`architecture-rule.md` §6.3's spirit, applied to the
   Engine boundary);
3. its public API has been **stable for one whole phase** — no signature change in the last
   phase's pull request.

Every lift is one Engine pull request (a `b` bump under the Engine's `release.md`, one `### Added`
entry) plus one app pull request (delete the copy, add the `RequiredEngineCapability` line,
`engine_capabilities.py` — `BOT-133`).

## 8.4 The Engine schedule, aligned with the application phases

| Engine step | When | Content | Tracked as |
| :-: | :--- | :--- | :--- |
| **E0** | now, independent of the app | `ScheduledJob.cancel()` (§7.8); nothing else — the Engine is not touched speculatively | note on `TASK-043` |
| **E1** | after app Phase 1 (two surfaces, two modules exist) | Lift `BoundedContextModule` (as `WorkbenchModule`), `IContributionRegistry`, `ContributionDescriptor`, `Place`, `SizeHint` into `sagittarius_engine/extensions/workbench/`. The Engine learns *the mechanism* of contributions; the app keeps *which* surfaces and kinds exist | `TASK-043` items 2 and 5 |
| **E2** | after app Phase 2 (strategy contributes into backtest's screen — a module-owned surface accepting foreign contributions) | Lift the surface runtime: a region host (the Engine's equivalent of `PageShell` with the place slots) and the per-place model the `EPIC-001D` constraints require | `EPIC-001D` objective 2 |
| **E3** | app Phase 5 | `NavigationService` (`USER_INTENT` vs `RESTORE`, `can_leave`), the screen lifecycle (`mount / unmount / ui_mode / shutdown`) and its conformance suite; `create_quick_widget(import_paths=)` when ADR D6 reopens; the UI runtime as a real `IExtension` | `TASK-043` items 1, 3, 5; `EPIC-001D` objectives 3–5 |

What never moves (§5.3): the module list, the set of surfaces, the contribution kinds
(`dev_probe` and the like), the `dev.mode` gate, the Binance gateway.

## 8.5 What this changes in the earlier text

- §5.3 said the two hooks `contribute` / `subscribe` stay in the app "until a second application
  needs them". Under the harvest rule the second *surface* in this application is enough evidence,
  so they lift at E1, not at some future application. §5.3 is superseded by §8.3.
- `EPIC-025F` (Phase 5) remains the app-side consumer task for E3; E1 and E2 are Engine pull
  requests that the app phases trigger, and they are listed in `EPIC-025`'s README as Engine
  milestones so the plan shows them.
