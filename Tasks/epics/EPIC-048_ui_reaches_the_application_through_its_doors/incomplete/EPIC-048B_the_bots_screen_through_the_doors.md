# EPIC-048B — The Bots screen reaches the application only through the doors, and renders exactly as before

**Status:** 🔵 Backlog
**Source:** the owner's delegation of 2026-10-24, settled as G6 and G9 of the EPIC-047 charter; the [decision record](../DECISION_2026-10-24_the_ui_reaches_the_application_through_its_doors.md) D5; De-risk R1 and A6/A7 ([DERISK §1, §8](../../EPIC-047_vps_bots_tab/DERISK.md)).
**Risk:** 🔴 — the Bots screen starts, resumes and judges real-money bots; moving the readiness assessment must not change a verdict.
**Complexity:** L — two new queries, the 24 application-service imports of the screen (10 of them computation), 8 port imports outside the allowlist, one adapter import, and five reads off the UI thread.
**Epic:** [EPIC-048](../README.md)
**SPEC:** [`SPEC-014`](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-048A](../completed/EPIC-048A_the_doors_rule_and_its_guard.md) (the guard that measures this task)

---

## 1. Context and problem
`bots/ui/bots_screen` holds 45 of R7's 215 bypass imports (DERISK §7.3, `5ddbd68`): 24 application-service imports (10 computation, over 8 names: `assess_readiness`, `assess_resume`, `field_verdicts`, `occupancy_of`, `account_view_of`, `state_words`, `failure_cause` and the `BotRunFactsReader` class), 17 port imports (8 outside the allowlist: `IVenueContexts` 3, `ISymbolCatalog` 2, `IVenueTradingPorts`, `IMarketDataSources`, `IMarketDataSync`), and the plan file the screen writes itself (`plan_export_flow.py`). R1 rendered the detail from six reads that crossed a JSON wire with no visible change (DERISK §1.3). Five reads still run on the UI thread (DERISK §8.1). EPIC-047 needs this screen to hold no host data except through queries and events.

## 2. Acceptance criteria
- [ ] `GetBotRunFactsQuery(bot_id, config)` returns the run facts (`RunFacts`, including occupancy) and replaces `BotRunFactsReader.read` at `selected_bot.py:196`. The query is read with the bot's other facts and held with them, so a 150 ms re-judge reads no host.
- [ ] `GetVenueChoicesQuery` returns each venue's connection state (a key is saved or not) and never a key; it replaces `venue_choice.py:95`'s read of the stored key on the UI thread. The venue symbol filters ride in `PlannerMarket.terms`, replacing `bots_dependencies.py:175`.
- [ ] The pure assessment (`detail_for`, `assess_readiness`, `assess_resume`, `field_verdicts`, `occupancy_of`, `account_view_of`, `state_words`, `failure_cause`) lives in the application layer as a pure read-model builder; it runs on the desktop over read models the screen holds, and the Plan still re-judges 150 ms after the last edit (`presenter_pacing.py:23`).
- [ ] The one query and the four non-query reads of DERISK §8.1 (`ExportBotPlanQuery`, the run facts, each venue's stored key, each venue's symbol filters, the strategy rows' wiring) run off the UI thread, fenced per `async-ui-action-rule.md`.
- [ ] The plan file is written behind the doors (a dispatcher call or an application service); `bots/ui/bots_screen` imports no adapter.
- [ ] The guard of EPIC-048A reads **0** imports outside the allowlist for `bots/ui/bots_screen`, and its baseline is lowered in this pull request.
- [ ] **No visible change** (EPIC-047 A7): the screen's existing tests are unchanged and green, and a before-and-after frame comparison of the draft, running, halted and unconnected states is identical. A test builds a `BotDetail` through a wire-shaped dispatcher and compares it with the in-process one (DERISK R1's test, kept as a regression test).
- [ ] A mainnet start or resume still asks for the venue confirmation, with the same words.

## 3. Design
G6 as worded in the EPIC-047 remote link record: every host fact reaches the screen through a query or an event; the pure assessment runs on the desktop. `detail_for` is a pure function of nine inputs, seven of them host facts, two local (`now`, the unsaved edits) (DERISK §1.5). The assessment moves as a function, not as a service the host runs (P3: one assessment, used by the Bots tab and later by the VPS tab). The two new queries follow the repository's use-case layout (`architecture-rule.md` §4). The screen's other dependencies stay local, as R1's table says: `feeds`, `ticks`, `symbols`, `workbench_ports`, the kinds, and the UI concerns.

## 3a. Reuse
Search `.claude/rules/capabilities.md` for an existing read model and fenced-read helper (`fenced_reads.py` already runs eight of nine queries on the pool): `used fenced_reads` for the moved reads; the new queries mirror `GetExchangeFactsQuery`. Record each catalog row checked.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/queries/get_bot_run_facts/` | the new query, its handler and result |
| `src/modules/bots/application/queries/get_venue_choices/` | the new query, its handler and result |
| `src/modules/bots/application/…` | the pure assessment, moved from `ui/` |
| `src/modules/bots/ui/bots_screen/` | the screen reads through the dispatcher; the reads leave the UI thread; no adapter import |
| `tests/unit/architecture/baseline_ui_doors.json` | lowered |
| `tests/…` | regression tests for each new query, the moved functions, and the wire-shaped detail |

## 5. Testing
Tier: unit and architecture, then the full gate. Map each criterion to a test or a frame comparison; name the mutation check for the moved assessment (change a threshold, see a test fail). Not run.

## 6. Docs touched
`Docs/MODULES/bots/05-building-blocks.md` and `Docs/MODULES/bots/06-runtime.md` (the new queries, the moved assessment and the thread of each read), per `task-execution-rule.md`.

## Implementation notes (written when done)
Not written: not started.
