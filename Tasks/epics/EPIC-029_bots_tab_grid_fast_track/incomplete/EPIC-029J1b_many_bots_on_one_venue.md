# EPIC-029J1b — Several bots run on different symbols of one venue, each within its own budget

**Status:** 🟡 In progress (implemented and proven on the fake exchange; waits for the `-Full` run and the reviewer)
**Source:** [`PRO-006`](../../../proposal/PRO-006.md) §4.3 "After the fast track", accepted by the user on 2026-10-03 (*"Oki, duyệt"*); split from `EPIC-029J` on 2026-10-17, when the owner chose J1a first (*"còn chuyện multibot thì làm J1a trước đi"*).
**Risk:** 🟡 — concurrency across several actors and several budgets on one account and one request-weight budget.
**Complexity:** M — lift the per-venue cap, measure tick fan-out and request weight, aggregate the budget across the bots of a venue.
**Epic:** [EPIC-029](../README.md)
**SPEC:** [`SPEC-014`](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [`EPIC-029J1a`](../completed/EPIC-029J1a_one_active_bot_per_venue.md) (one active bot per venue, done). `EPIC-029H` is not awaited (owner, 2026-10-17).

---

## 1. Context and problem
J1a made the cap one active bot per venue (`other_active_bot`). Two bots on one venue are still refused, though the entity, ids, store, tags and budgets are already per bot. This task lifts the per-venue cap for bots on **different symbols** of the venue and proves isolation. The symbol lease (trading's, per venue) stays the rule that keeps two bots off one symbol.

What J1a's audit found that this task must settle (evidence in J1a's notes):
- **A per-venue request-weight gate exists** (`ExchangeCallPolicy` / `RateLimitGate`, `exchange_call_policy.py`, `EPIC-035D`, `BUG-216`): it closes the venue's requests to the minute's end at 70 % of the exchange's weight and for a rate limit's or ban's stated pause, for every caller on the venue. So a closed gate already refuses every bot of the venue. What is open is the *bots'* reaction (each bot halts `RATE_LIMITED` separately, `grid_rate_limit_pause.py`) and a weight budget shared between bots *before* the 70 % line; build on the gate, not beside it.
- **The order pacer is per bot** (`MonotonicOrderPacer`, built per executor), so two bots of one venue do not space their orders against each other.
- **The owner budget's caps apply to each bot's own budget**, not to the sum of the bots of a venue.
- **Latent risk carried from `EPIC-042E`:** `--resume-halted` touches no other state only while no second bot can be active beside a HALTED one on its venue; its Resume opens the venue's order session, whose switch-on reconciles every RECOVERING bot of that venue. Several bots on one venue re-open the question whether a halted-bot resume may reconcile a RECOVERING bot the owner left for `--resume-recovering` (O2).

## 2. Acceptance criteria
- [x] Several bots run on different symbols of one venue; each one's orders, fills and PnL are attributed by its tag and never by another's. *`test_several_bots_on_one_venue_run_together_on_the_fake_exchange.py`: three Futures symbols, then BTCUSDT + ETHUSDT at their own prices; a fill on one symbol changes only that bot's runtime.*
- [x] Starting a bot on a symbol another bot holds is refused, naming the holder: the bot id from the bots' world (`ONE_ACTIVE_BOT_PER_SYMBOL`), the lessee from the lease (`SYMBOL_LEASED`, "BTCUSDT is held by strategy.x"). *Same file; unit: `test_other_active_bot_and_budget.py`, `test_bot_readiness_assessment.py`.*
- [x] Tick fan-out to N bots is measured (N = 1, 5, 20) before the cap is raised; the result is recorded and the chosen cap justified by it. *§5a: about 50 µs a tick at every N; not a limit.*
- [x] Request weight of N bots on one venue is measured on the fake exchange's `WeightMeter` against the existing `RateLimitGate`; whether a weight budget shared before the 70 % line (or venue-wide pacing) is needed is decided from it. *§5a, §3b: the cap, the gate and a venue-wide order pacer are enough; no shared weight allowance.*
- [x] A rate limit met by one bot: what its neighbours do is settled and proved. *§3b; `test_a_rate_limit_met_by_one_bot_halts_its_neighbours_on_the_fake_exchange.py`. **This changes the criterion the J1a author wrote** ("its neighbours halt `RATE_LIMITED` too, not only be refused at the gate"): a neighbour halts at the first order it needs, and a bot that only reads keeps its ladder; reason in §3b.*
- [x] An Emergency Stop halts every bot on that venue and none on the other. *Same file as the first item: three Futures bots `HALTED` `SWITCH_OFF` with no order resting, the Spot bot `RUNNING` with its ladder.*
- [x] The owner budget caps and the `EPIC-042E` latent risk: what was found, with evidence, and fixed here or named. *§3c.*
- [x] The cap is the owner's choice. *Asked on 2026-10-17 with the §5a figures; answered: **5 bots, a budget per bot** (recommended option), quoted in §3b.*

## 3. Design (written 2026-10-17, before the code, against `4847277`)
**The rule.** `other_active_bot` keeps its place and changes its question: *which other bot, not at rest, holds this venue **and this symbol***. Two bots on different symbols of a venue no longer block each other; the symbol lease (`TradingSessionState.claim_symbol`, per venue) is still the rule that keeps two bots off one symbol, and the readiness item now names the holder in both places (the bot id from the stored world, the lease owner from trading). A second function in the same file counts the other active bots of the venue against one named constant, `MAX_ACTIVE_BOTS_PER_VENUE` (domain), so the number of bots on an account is a decision in one place. A file the store refused still counts as holding every symbol (worst case), and does not count toward the cap.

**What is shared, what is not (by the code, not by guess).**
| Thing | Today | This task |
| :--- | :--- | :--- |
| Tick fan-out | `BotEventRouter.on_tick` filters executors by symbol, venue and market type *before* anything is queued | measured at N = 1, 5, 20; no change unless the numbers ask |
| Fill, order end | routed by the order's tag, O(1) | unchanged |
| Emergency Stop / switch | `BotExecutors.on_venue(venue)` | proved for N bots on a venue and none on the other |
| Request weight | one `RateLimitGate` per venue, 70 % line | measured on `WeightMeter` for N bots (start, steady, fill burst, simultaneous resume) |
| Rate limit met by one bot | the gate refuses every caller; a neighbour halts `RATE_LIMITED` at its own next request and resumes by `grid_rate_limit_pause` | settled in section 3b |
| Order pacer | one `MonotonicOrderPacer` per bot | one per venue, thread-safe (section 3b) |
| Owner budget caps | per bot's budget | section 3c |

**3b. Decisions taken from the numbers (§5a).**
- **The cap is 5 active bots per venue** (`MAX_ACTIVE_BOTS_PER_VENUE`). Owner decision, 2026-10-17, on the question "how many bots may run together on one venue?" with the §5a figures: *"5 bot, ngân sách riêng từng bot (Khuyến nghị)"*. It is a real-money choice (it bounds how much one account has working), so it was asked, not defaulted. The owner also chose **no sum cap on the bots' capital and no shared weight allowance**: each bot keeps its own budget; what bounds the account is the number of bots times the capital the owner gives each.
- **Why 5 is where the numbers stop.** Idle Futures bots cost 175 weight a minute each, linear in N: five use 875, 52 % of the gate's 1,680 line, leaving about 800 for a start (about 300) and a burst of fills (19 each); ten bots idle reach 1,750, past the line, so the gate would close on idle reads alone; twenty reach 3,500, past the exchange's own 2,400. `test_a_full_venue_of_idle_bots_leaves_the_gate_the_room_its_starts_and_fills_need` holds that margin: it fails if five idle bots ever spend more than 60 % of the line.
- **Tick fan-out needs no filter by symbol "before queueing" beyond the one that exists.** `BotEventRouter.on_tick` already selects the executors of the tick's symbol, venue and market type before `facts.on_tick` queues anything. Measured: 46, 53, 49 µs a tick at N = 1, 5, 20, and each bot hears only its own ticks (asserted by wrapping the real `facts.on_tick`).
- **A weight budget shared before the 70 % line is not built.** The gate already shares the venue's weight between every caller, and the cap keeps idle bots at about half the line. What would help more is fewer reads (`BOT-184`: one position read per beat for all bots), not a second allowance.
- **Venue-wide order pacing is built, on the existing pacer.** The exchange limits orders per account; the `EPIC-029A` notes put one bot at 40 orders per 10 s by spacing against Spot's documented 50 per 10 s per account (not verified live), so two bots laying ladders together could already exceed it. `MonotonicOrderPacer` now reserves a turn under a lock and `VenueOrderPacers` hands one to every bot of a venue; the venue's orders keep 250 ms apart, 40 per 10 s, whatever N. The price is latency: a 20-order ladder takes 5 s and a neighbour's orders queue behind it. No second limiter: the gate (weight) and the pacer (orders) are two budgets of the exchange.
- **A rate limit one bot meets: the neighbours react at their own next request, and nothing halts earlier.** The gate refuses every caller of the venue. A neighbour that needs an order (its fill's counter) halts `RATE_LIMITED`, not `ERROR` and not `SWITCH_OFF`, and schedules its own resume; a neighbour that only reads (the beat's position and mark reads) logs that it could not read and keeps its resting ladder (proved). Halting it proactively was rejected: a halt for a rate limit sends nothing and cancels nothing (a cancel would be refused too), so it protects no exposure, and its resume is a cancel-all and a fresh ladder, which costs weight and fees at the one moment weight is scarce. This is what a single bot already did; N bots add no case.
- **The resumes are not staggered.** Every halted bot resumes at the same instant (pause plus the 2 s margin), measured in the same test. The reconcile of N bots at once costs 76 weight each (381 at 5, 1,521 at 20): at the cap of 5 that is 23 % of the line. Beyond about 15 bots the herd alone would approach the line; that is a limit of this cap, to revisit with `BOT-184`.

**3c. Owner budget caps and the `EPIC-042E` latent risk.**
- **Owner budget caps.** Found: `RegisterOwnerBudgetCommandHandler._cheap_refusal` compares one bot's budget with `OwnerBudgetCaps.exceeded_by`, three ceilings per budget (100 open orders, 250 ms spacing, 60 orders a minute); nothing sums the books of a venue (`src/modules/trading/application/session/register_owner_budget/handler.py`). Consequences at 5 bots: up to 500 open orders and 300 orders a minute *by the budgets*; the order rate is in fact bounded by the venue pacer (240 a minute), the open orders are bounded by the exchange per symbol (each bot has its own symbol), and the money by the capital the owner types per bot, checked at Start against the account's available quote or margin, which already nets what the other bots locked, since a grid places its whole ladder at Start. Decision (owner, §3b): no sum cap. Not built, by that decision.
- **The `EPIC-042E` latent risk is real, and was reproduced.** On the fake Spot venue after a restart with one bot `RECOVERING`, starting a bot on another symbol opened the venue's order session and the first bot went to `RUNNING` with its ladder laid: `BotEventRouter.on_switch` posts the switch-on to every executor of the venue and `GridFacts._apply_switch` reconciles a `RECOVERING` one. Fixed here **for Start**: `venue_recovering` and the readiness item `RUN_VENUE_RECOVERING` (`BotRefusal.VENUE_RECOVERING`) refuse a Start while any bot of the venue is `RECOVERING`, which is exactly what J1a's one-bot rule did by accident; proved by `test_a_bot_waiting_to_recover_holds_back_a_start_on_its_venue_until_it_is_resumed`. On Futures the first opening was already refused (`unexpected_positions`: the recovering bot's position is not yet an owner's). **Not fixed, named: `BOT-183`** — a Resume of a `HALTED` bot, `--resume-halted` and the operator's `bot stop` open the same session. The mechanism fix is to say for whom the session opened (a field on `TradingSwitchChangedEvent` and a parameter on `ensure_ready`, a change to the `trading` port and every implementer and fake) and needs the owner's answer on ADR 038 O2 for the desktop, so it is its own task; the runbook tells the owner to resume recovering bots first meanwhile.

## 3a. Reuse
`ExchangeCallPolicy` / `RateLimitGate` for request weight and rate limits (not a second limiter); `grid_rate_limit_pause` for the bots' pause; `MonotonicOrderPacer` made venue-wide instead of a second pacer; `WeightMeter` of the fake exchange for the weight figures; `booted_two_venues` / `booted_futures_bots` worlds for the composed-app proofs.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/services/lifecycle/other_active_bot.py` | `BotSlot`; `other_active_bot` now per venue **and symbol**; `venue_is_full`, `venue_recovering`, `VenueOccupancy`, `occupancy_of` |
| `src/modules/bots/domain/venue_bot_cap.py` (new) | `MAX_ACTIVE_BOTS_PER_VENUE = 5`, the owner's number |
| `.../readiness/bot_readiness_reader.py`, `bot_run_facts.py`, `readiness_assessment.py`, `bots/ui/bots_screen/selected_bot.py` | the Start path, the readiness reader and the screen read `occupancy_of`; items `RUN_OTHER_BOT_ACTIVE` (names the symbol), `RUN_VENUE_FULL`, `RUN_VENUE_RECOVERING`; the lease item names the lessee and is not repeated when the holder is the active bot |
| `src/modules/bots/contracts/bot_command_result.py` | `ONE_ACTIVE_BOT_PER_VENUE` renamed `ONE_ACTIVE_BOT_PER_SYMBOL`; `VENUE_FULL`, `VENUE_RECOVERING` |
| `.../kinds/grid/start/grid_start_preconditions.py` | the lease race refusal names the holder |
| `src/modules/bots/adapters/monotonic_order_pacer.py`, `venue_order_pacers.py` (new), `.../grid_executor_factory.py`, `bots/composition/executor_bindings.py` | one thread-safe pacer per venue; `GridExecutorDeps.pacers` takes the venue |
| `scripts/render_bots_design_tables.py` | the cap row of the timing table |
| `tests/sanity/fake_exchange/futures_market.py`, `futures_routes.py` | 19 more Futures symbols (`CROWD_SYMBOLS`) that list and trade like `BTCUSDT` |
| `tests/...` | §5 |
| `Docs/...`, `Tasks/...` | §6 |

## 5. Testing
Unit (`tests/unit/modules/bots`, 4 054 tests green before the last additions; the rule's own file `test_other_active_bot_and_budget.py`, the readiness items in `test_bot_readiness_assessment.py`, screen and Start parity in `test_the_screen_and_start_read_the_same_world_the_same_way.py` with four new scenarios, the pacer in `test_monotonic_order_pacer.py` and `test_venue_order_pacers.py`). Integration on the composed app over the fake exchange (`booted_two_venues`, real adapters): `test_several_bots_on_one_venue_run_together_on_the_fake_exchange.py` (attribution, the holder named, the lessee named, the cap and a place freed by a stop, fills reaching one bot, a stop leaving the others, an Emergency Stop on N bots and none of the other venue, a recovering bot holding back a Start), `test_a_rate_limit_met_by_one_bot_halts_its_neighbours_on_the_fake_exchange.py`, `test_many_bots_on_one_venue_cost_on_the_fake_exchange.py` (the measurements). Mutation checks done: `slot.symbol == symbol` → `True` (10 red), `>=` → `>` in `venue_is_full` (1 red), the `RECOVERING` test → `True` (13 red), the pacer's lock removed (the threaded test was red before the fix); each restored. The Testnet tier is not run: this task adds no exchange behaviour the fake does not model, and the fake's weights and limits are Binance's documented ones, not verified live.

## 5a. Measurements (how they were taken, what they mean)
Taken on 2026-10-17 on the composed app over the fake exchange, Futures Testnet, one grid of 4 levels per bot (`GRID`), N distinct symbols at one mark; request weight from the fake's `WeightMeter` (`tests/sanity/fake_exchange/request_weight.py`, Binance's documented weights); command: `pytest tests/integration/modules/bots/test_many_bots_on_one_venue_cost_on_the_fake_exchange.py -k measured` (each figure is written on the terminal). The gate's 70 % line and the cap are lifted for these runs so a figure is not cut off. Futures limit 2,400 a minute; the gate closes at 1,680.

| N bots | Tick fan-out (per tick) | Start, all N (per bot) | Idle for a minute (per bot) | One fill beside N | Restart: N reconcile (per bot) |
| :-: | :-: | :-: | :-: | :-: | :-: |
| 1 | 46 µs | 357 (357) | 175 (175) | 19 | 77 (77) |
| 5 | 53 µs | 1,537 (307), 91 % of the line | 875 (175), 52 % | 19 | 381 (76), 23 % |
| 20 | 49 µs | 5,974 (299), 356 % | 3,500 (175), 208 % of the line, 146 % of the exchange's limit | not taken | 1,521 (76), 91 % |

Reading: fan-out is flat and cheap. Weight is what limits N: idle reads grow linearly (`positionRisk` 120 of the 175, then `premiumIndex`, `openOrders`, `openAlgoOrders`), a Start burst is limited by the gate and the single start lock (eight starts inside a minute with the real gate: 6 accepted, 2 refused "exchange asked for a pause", 1,681 weight spent of the exchange's 2,400, `test_a_burst_of_starts_stops_at_the_gate_before_the_exchange_limit`), and a fill costs what it costs alone. Wall-clock figures are those of this container and prove only the order of magnitude; the weights are exact for the fake's table.

## 6. Docs touched
`Docs/SPEC/SPEC-014_run_a_grid_bot.md` §5 (the Run items), `Docs/OPERATIONS/headless_runbook.md` §8 ("Bots on more than one venue, and several on one"), `Docs/MODULES/bots/06-runtime.md` ("Built: Start", new "Built: several bots on one venue") and `10-quality.md` (the cap row, generated), `Docs/VOCABULARY/README.md` (**Venue slot** changed, **Venue order pacer** new), ADR 029 D20's note, this epic's README and TRACKING.

## Implementation notes (written when done)
- The first thing the measurement showed was not in the plan: with five Futures bots started inside a minute the weight gate closed on the sixth call and a bot's stop waited out the pause. Start costs about 300 weight (15 reads of `/fapi/v2/account`, 11 of `positionRisk`, 3 of `commissionRate`, per start), so a journey that starts several bots lifts the gate's line (`weight_gate_lifted`) and the gate has its own tests.
- A bot's tag is still what separates its orders: the integration files use distinct symbols but assert on `tag_of(client_order_id)` and on the runtime, not on the symbol.
- The rename `ONE_ACTIVE_BOT_PER_VENUE` → `ONE_ACTIVE_BOT_PER_SYMBOL` was grepped across `src`, `tests`, `Docs`, `Tasks` (J1a's completed file keeps the name it shipped with).
- **Observed, not investigated (not this task's):** after an Emergency Stop on the fake Futures venue the bot's runtime still holds its inventory while the fake's position is flat, and a Resume then Confirm places a reduce-only sell the exchange rejects (`-2022`), which sends the bot to `ERROR`. It may be the fake closing the position where the real adapter leaves it open, or a real defect in the resume proposal; a Futures Testnet run would tell. It is why the resume of N halted bots is not among the measurements (the restart reconcile is).
- Not done, by decision: a venue-wide capital cap and a shared weight allowance (owner, §3b); proactive halting of neighbours (§3b); staggering the resumes (§3b); `BOT-183` and `BOT-184`.
- Gate evidence: the commit tier (`ci-local.ps1 -SkipTests`) is PASS on the pushed head; the `-Full` run is the pull request's check.

## Resume (optional; while unfinished)
Waiting for the pull request's `ci-local.ps1 -Full` run and the reviewer's verdict. Then: move this file to `completed/`, set `✅ Done (date)` and the epic README row.
