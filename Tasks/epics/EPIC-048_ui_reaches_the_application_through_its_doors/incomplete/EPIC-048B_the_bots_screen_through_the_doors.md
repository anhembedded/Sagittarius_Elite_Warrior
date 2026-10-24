# EPIC-048B — The Bots screen reaches the application only through the doors, and renders exactly as before

**Status:** 🟡 In progress — PR 1 of 2 (the queries and the assessment behind the doors)
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
- [ ] The guard of EPIC-048A reads **0** imports outside the allowlist for `bots/ui/bots_screen`, except the four public market-data ports held only by the container-taking composition files (`ISymbolCatalog` ×2, `IMarketDataSources`, `IMarketDataSync`) and the four container-taking functions, which [EPIC-048C](EPIC-048C_presenters_receive_a_narrow_gateway.md) closes with the strategy rows' wiring read (coordinator's decision of 2026-10-24, under the owner's delegation; the allowlist is not widened). The baseline is lowered in each pull request by what that pull request removed, never more.
- [ ] **No visible change** (EPIC-047 A7): the screen's existing tests are unchanged and green, and a before-and-after frame comparison of the draft, running, halted and unconnected states is identical. A test builds a `BotDetail` through a wire-shaped dispatcher and compares it with the in-process one (DERISK R1's test, kept as a regression test).
- [ ] A mainnet start or resume still asks for the venue confirmation, with the same words.

## 3. Design
G6 as worded in the EPIC-047 remote link record: every host fact reaches the screen through a query or an event; the pure assessment runs on the desktop. `detail_for` is a pure function of nine inputs, seven of them host facts, two local (`now`, the unsaved edits) (DERISK §1.5). The assessment moves as a function, not as a service the host runs (P3: one assessment, used by the Bots tab and later by the VPS tab). The two new queries follow the repository's use-case layout (`architecture-rule.md` §4). The screen's other dependencies stay local, as R1's table says: `feeds`, `ticks`, `symbols`, `workbench_ports`, the kinds, and the UI concerns.

**The assessment reads no host (`AssessBotQuery`).** Its handler takes no constructor dependency and is a pure function of the query's fields, so a remote backend ([EPIC-047](../../EPIC-047_vps_bots_tab/README.md)E) answers the host-fact queries (`GetBotRunFactsQuery`, `GetPlannerMarketQuery`, `GetExchangeFactsQuery`, `GetPlanRiskFactsQuery`, `GetVenueConnectionQuery`, `ListBotsQuery`) over its link and leaves this one to the local dispatcher. `test_assess_bot.py::test_the_assessment_holds_no_port` fails the day the handler is given a collaborator that could read a host.

## 3a. Reuse
Search `.claude/rules/capabilities.md` for an existing read model and fenced-read helper (`fenced_reads.py` already runs eight of nine queries on the pool): `used fenced_reads` for the moved reads; the new queries mirror `GetExchangeFactsQuery`. Record each catalog row checked.

Checked (PR 1): `ICommandDispatcher` row — used, both new queries are dispatched through it; `UiThreadRelay` / `FencedReads` — not used yet, PR 2 moves the Run facts read onto it; `price_text` / `money_text` — not needed, no number is written. No row fits "a pure handler answered locally"; the shape is the repository's CQRS query (`architecture-rule.md` §4) with a handler that reads nothing. `BotRunFactsReader` and `occupancy_of` are reused by the new handler, not copied; `list_bots.listed` was extracted so the list and the Run facts name bots in one order.

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
Written so far for PR 1 (commits `6ae7c03`, `3e564be`, `8367918`); completed with PR 2.

**Split** (sent to the coordinator before building): PR 1 — the read models, `GetBotRunFactsQuery` and the assessment behind `AssessBotQuery`, at the same timing as before; PR 2 — the reads off the UI thread (Run facts, venue choices with `GetVenueChoicesQuery`, `ExportBotPlanQuery`), the filters from `PlannerMarket.terms`, the plan file behind a command.

**Decisions (agent, under the Constitution):**
1. **Values and words go to `bots/contracts/`, computation stays in the application layer.** `ConnectionRead`, `ConnectionState`, `RunFacts`, `MARKET_NOT_READ`, the connect-failure words and `account_view_of` are values, vocabulary or a value mapping both the Start path and the screen hold (P3); trading's `connection_failure_words` is the precedent. `readiness_assessment` imports them back, so the Start path and its tests keep their names. `assess_readiness`, `assess_resume`, `field_verdicts`, `occupancy_of` and the budget judgement stay in the application layer and are reached through queries (D5).
2. **`detail_for` stays in `ui/`.** It is the presentation of the assessment (tones, words of the formatter, plan checks, availability) and imports `support/ui_kit`, which the application layer may not. What D5 calls the assessment is the part that judges host facts; it moved behind `AssessBotQuery`. `detail_for` takes it as a parameter (`Assess`).
3. **`AssessBotQuery` is a query, not a new allowlisted port.** A pure handler dispatched where the screen runs keeps D1 literal (no rule change) and keeps the 150 ms re-judge free of host reads. A remote backend answers it locally, as it keeps the kinds local (D2); the query reads nothing, and `IBotKind` travels as itself.
4. **`GetBotRunFactsQuery(bot_id, venue, symbol)`, not `(bot_id, config)`.** The budget depends on the parameters on screen; the query carries the caps (`BotRunFacts.caps`) and `run_facts_for` judges the budget locally, so an edit never asks the host. The other bots are read from the store in the list's order (`list_bots.listed`), which is the order the screen named them in.
5. **A Run step not yet read waits.** `AssessBotQuery` with `run=None` adds one item, `RUN_FACTS_READING` (`READING_THE_RUN_FACTS`), so Start is never offered on facts nobody read. PR 1 never shows it (the read is still synchronous); PR 2's asynchronous read does, for the moment the read is in flight. This is the one new wording, and it only blocks.
6. **`GetVenueChoicesQuery` moved to PR 2.** Built first in PR 1, it broke `test_bots_failures.py::test_a_command_that_raised_is_a_message_box_whose_headline_has_no_exception`: the test fails every dispatch, and New bot read its choices through the dispatcher at the click. The read belongs with PR 2's asynchronous reads, where New bot uses the choices the screen holds.

**Verification (PR 1):** the frame comparison (37 frames and model states: every `preview_frames`, `plan_dock_frames`, `plan_table_frames` and `centre_tab_frames` frame, the preview, and the real screen over the module's object graph for draft, refused draft, running, halted, a symbol held by another bot, a venue not enabled, a refused key and an edit over the levels) is identical pixel for pixel and field for field before (`bfae44f`) and after. Mutation checks on the moved assessment, each killed by `test_assess_bot.py`: Grid budget `grid_count + 1` → `grid_count`; trading cap `>` → `>=`; the waiting item removed; the RUN_STARTING_STATES gate removed. DERISK R1's test is kept as `test_the_detail_through_a_wire_equals_the_detail_in_process.py` (host queries by name, as bytes; it fails when the Run facts do not reach the detail).

**Tests whose construction changed (no assertion changed):** import paths of moved code (`test_margin_view.py`, `test_one_connect_failure_one_paragraph.py`, `test_the_screen_and_start_read_the_same_world_the_same_way.py`, `test_bot_recorded_inventory.py`); `detail_for` callers pass the assessment (`test_the_plan_of_a_triggered_grid.py`, `test_a_halted_futures_bot_is_judged_by_its_own_venue.py`, `test_the_plan_says_what_the_stop_and_the_take_profit_are_worth.py`, `test_the_plan_group_shows_the_draft_not_the_saved_config.py`, the maker-rate integration test); `SelectedBot` callers pass a dispatcher (`test_selected_bot_shares_plan_facts.py`, `test_the_plan_group_…`, `test_sandbox_session.py`); the screen/Start parity test now reads the Run facts through the query, the screen's own path. The fixture `BotsScreen` gained `kinds`.

**Guard, `bots/ui/bots_screen`:** around the doors ADAPTER 2, APP_SERVICE_fn 10 → 0, PORT 8 → 7; data APP_SERVICE_data 14 → 0, APP_OTHER_data 2; CONTAINER 4 (048C).

## Resume
PR 2 from the head of PR 1: (1) `GetVenueChoicesQuery` (handler over `IVenueContexts` and the kind catalog; answer `VenueChoice`, never a key) read on the pool; New bot offers the held choices; (2) the Run facts read on `FencedReads` as `ReadKind.RUN`, held in `SelectedBot`, re-read on select, list answer, action finished and the clock; (3) `ExportBotPlanQuery` on the pool; (4) the plan file written by a command; (5) the venue filters from `PlannerMarket.terms`. Then the remaining ports (`ISymbolCatalog` ×2, `IMarketDataSources`, `IMarketDataSync`) with the coordinator's answer.
