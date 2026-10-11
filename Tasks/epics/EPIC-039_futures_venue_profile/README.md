# EPIC-039 — Every bot kind runs on Spot or Futures through one venue profile; the Grid is the first to use it

- **Status:** 🔵 Planned — scaffolded 2026-10-10; **not started** (documentation only; the owner asked for the epic to be written and pushed)
- **Repositories:** Elite. No Engine change is expected; one that might help is listed as a question in [`DECISION`](DECISION_2026-10-10_futures_venue_profile.md) and needs its own confirmation (`ONBOARDING.md` §2).
- **Origin:** the owner, 2026-10-10: *"nếu bot grid thêm option future thì cần gì? design như nào? cần thêm các option nào, và cần đưa những phần nào về chung … mục tiêu là tôi muốn thêm bot nào cũng sẽ có phần future vs spot"* (translated: if the Grid bot gets a Futures option, what is needed, how to design it, which options to add and which parts to make shared — the goal is that **any bot added later has both a Futures and a Spot side**), then *"ok, sau đó mở epic cho cái này"* (open an epic for it). Supersedes [`EPIC-029K`](../EPIC-029_bots_tab_grid_fast_track/cancelled/EPIC-029K_grid_on_futures.md), which scoped Futures as one Grid-only task.
- **North star:** [`DESIGN_2026-10-10_futures_venue_profile.md`](DESIGN_2026-10-10_futures_venue_profile.md) — the verified current state, the shared ports, the direction model, the risk guard, the sequences, the extension cases. Sources: [`RESEARCH_2026-10-10_futures_grid.md`](RESEARCH_2026-10-10_futures_grid.md). Choices still open: [`DECISION_2026-10-10_futures_venue_profile.md`](DECISION_2026-10-10_futures_venue_profile.md).
- **Tracking:** [`TRACKING.md`](TRACKING.md).
- **Dependencies:** `EPIC-029H` (the Spot Grid soak; its results decide how much of the Spot executor is trusted as the model); [`EPIC-026K`](../EPIC-026_road_to_real_money/incomplete/EPIC-026K_exchange_side_protective_stop.md) (exchange-side stop — required before Futures leverage above 1 on mainnet); [`EPIC-036`](../EPIC-036_alerting_module/README.md) (new alert kinds: liquidation risk, margin); [`EPIC-038`](../EPIC-038_headless_operation/README.md) (a headless `run` host must stop a Futures bot differently from a Spot one — see [DESIGN §12](DESIGN_2026-10-10_futures_venue_profile.md)); [`EPIC-037`](../EPIC-037_ai_development_leverage_points/README.md) (its "only one" guard idea is reused for the profile).

---

## 0. How to work this epic (read this first if you are the implementing session)

**Reading order, before any edit** (`CLAUDE.md` → `.claude/ONBOARDING.md` are loaded already):
1. This README, then [`DESIGN`](DESIGN_2026-10-10_futures_venue_profile.md) §1 (what exists, with `file:line`) and §3 (the shared ports), then [`DECISION`](DECISION_2026-10-10_futures_venue_profile.md) §4 (which questions the owner has answered — **never decide an open one yourself; ask**, with options and a recommendation, per `.claude/rules/report-rule.md` §2).
2. `.claude/skills/execute-task/SKILL.md` and `.claude/rules/task-execution-rule.md`; `.claude/rules/architecture-rule.md` (layers, ports, "Seam now, variant later" §7.2.1); `.claude/rules/domain-truth-rule.md`; `.claude/rules/testing-rule.md`; `.claude/rules/ci-rule.md` §1 (the commit tier).
3. The task file you are about to do, **including its "Facts verified" and "Pitfalls" sections**, then the files its "Read first" list names. Cited `file:line` values were true on `master-warrior` `076d339` (2026-10-10); re-check each with `grep` before relying on it, and say in the task's notes when one moved.

**Order of work:** the dependency column of §4, one task per pull request, in this order unless the owner says otherwise: `039A → 039B → 039C → 039D → 039E → 039G → 039F → 039H → 039J → 039I → 039K → 039M → 039L`. Show the Mermaid Kanban and Gantt of the epic before starting a task (`.claude/rules/report-task-rule.md`); [`TRACKING.md`](TRACKING.md) has the Gantt.

**Rules that apply to every task here, and the traps this codebase has set before:**
- **Spot must not change.** Phases A–B are refactors under green Spot tests; a Spot bot's orders, state files and log lines are byte-for-byte what they were. Every task that touches shared code ends with the Spot integration journeys (`tests/integration/modules/bots/`) green, **and** names the test that would have gone red had the Spot behaviour moved.
- **No real exchange, ever, in this epic's tests.** The Futures fake (`tests/sanity/fake_exchange/`) is extended in `039C`; Testnet runs are the owner's, recorded in a task by the owner (`tests/testnet/` is opt-in, `ci-rule.md` §2).
- **A port that gains an `@abstractmethod` changes every implementer in `src/`, `scripts/` and `tests/` in the same commit** (`architecture-rule.md` §2, `BUG-026`).
- **Modules talk through `contracts/` only**; `bots` never imports `trading/application` or `trading/adapters`; trading remains the only module that sends orders (`DESIGN §3`). The module-boundary allowlist only shrinks (`test_module_boundaries.py`).
- **Domain files are Qt-free and immutable-by-value** (`domain-truth-rule.md`); money is `Decimal`, never `float`; a missing exchange fact is a named state, never zero (`bot_kind_inputs.py`, `exchange_facts.py` pattern).
- **Do not guess an exchange rule.** Where the DESIGN says *to verify*, read Binance's official USDⓈ-M Futures documentation (https://developers.binance.com/docs/derivatives/usds-margined-futures/) and record the page and the finding in the task's notes before coding; some of that site's pages did not render in the research session ([RESEARCH §8](RESEARCH_2026-10-10_futures_grid.md)).
- **Commit format, authority and the gate:** `.claude/rules/commit-rule.md` (Conventional Commits, both trailers); commit and push to your own branch are free after the commit tier (`pwsh scripts/ci-local.ps1 -SkipTests` + `pytest tests/unit/architecture -q` + the touched tests); open a **feature PR**, spawn a reviewer in the turn that pushes (`ONBOARDING.md` §7); the user merges; the `-Full` run is GitHub Actions'. Dependencies (`requirements*.txt`) and `.claude/settings.json` need the owner's approval first.
- **Board bookkeeping:** moving a task file to `completed/`, its `Status:` line, the README row, `TRACKING.md`, and `Tasks/epics/README.md` (`ONBOARDING.md` §6; `test_task_board_is_consistent.py`).
- **Language:** English in every file, comment, commit and log line; conversation with the owner in Vietnamese.

## 1. Why now, in one example
The owner's Spot Grid `ke95g7` (ETHUSDT, `spot_mainnet`) halted at 21:11:18 with `price_feed_stale: last tick 62 s ago; the limit is 60 s`, cancelled its six ladder orders and **left 0.0068 ETH held with no order protecting it** (the owner's log, 2026-10-09). On Spot that is an unprotected holding. On Futures the same *halt-and-cancel* policy would leave a **leveraged position with no stop**, where the loss is a multiple of the move and the end state is liquidation. Futures cannot be added by copying the Spot executor; the exposure model, the risk guard, the stop and the reconcile all change meaning, and every future bot kind will meet the same fork. The fork is therefore made once, in shared ports, and each kind plugs into it.

## 2. Decisions already made
1. **Futures is a venue profile, not a second bot kind, and the profile is shared by every kind** (the owner, 2026-10-10, accepting the evaluation; consistent with `EPIC-029K`'s earlier note and `IBotKind`'s docstring). A kind declares which profiles it supports and uses the shared ports; it never asks `market_type is SPOT` (`DESIGN §3`).
2. **One planner for all directions.** Long, Short and Neutral differ only in how much exposure the bot opens at start (`DESIGN §5`); Spot Grid is Long at leverage 1 and is the **regression oracle** for the generalised planner.
3. **One-way position mode only** in this epic; the connection check already refuses Hedge Mode (`ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED`).
4. **USDⓈ-M perpetuals only** (`MarketType.FUTURES_USD_M`); Coin-M and delivery contracts are out.
5. Everything else (first direction, capital semantics, mandatory stop loss, out-of-range behaviour, mainnet gating, the stop policy a headless host applies to a Futures bot) is **open** and listed with a recommendation in the decision record. Nothing is decided by the epic's author.

## 3. Goals — measurable
| Metric | Today (measured 2026-10-10, `master-warrior` `076d339`) | When the epic is done |
| :--- | :-: | :-: |
| Places in `bots/` that hard-code Spot (`MarketType.SPOT`, `SpotHolding`) | 9 outside `ui/` and 6 in `ui/` (the exact list is `DESIGN §1.2`) | 0 outside the one profile adapter; a guard test fails on a new one |
| Venues a bot can be created on | 2 (Spot testnet, Spot mainnet) | 4 (adds Futures testnet, Futures mainnet), mainnet Futures behind the gate of `039L` |
| Directions a Grid supports | 1 (long, implicit) | 3 (long, short, neutral) on Futures; long only on Spot, stated by the profile |
| What a Futures plan is judged on before Start | nothing (no Futures bot exists) | liquidation distance against the stop loss, leverage bracket, margin, foreign position, settings drift — as verdicts, same shape as the Spot checks |
| What a Futures bot does when it halts | not defined | a position never stands without an exchange-side stop (`039L`); the halt policy is explicit per profile |
| Cost model | Spot: maker/taker only | + Futures commission from the account, funding every 8 h, realized profit; shown and counted in PnL |
| Fake exchange: Futures resting LIMIT orders | never fill (`order_book_state.py` docstring) | fill on a price cross, with positions, funding and liquidation, so the executor is tested end to end |
| A new bot kind's Futures support | not possible | one declaration (`supported profiles`) plus a conformance suite that every registered kind passes |

## 4. Sub-tasks, ordered by risk
Do them in the order in §0 (dependencies), not in this table's order.

| Id | Task | Repo | Depends on | Risk | Status |
| :--- | :--- | :--- | :--- | :-: | :--- |
| [EPIC-039D](incomplete/EPIC-039D_exposure_book_for_positions.md) | Exposure book and owner budget for a signed position (trading side), reconcile against the exchange, foreign-position rule | Elite | 039A, 039C | 🔴 | Planned |
| [EPIC-039F](incomplete/EPIC-039F_risk_guard_and_liquidation.md) | Risk guard: liquidation distance as plan verdicts, a runtime guard on the exchange's liquidation price, thresholds, alert kinds | Elite | 039E, 039G | 🔴 | Planned |
| [EPIC-039H](incomplete/EPIC-039H_futures_grid_long.md) | Futures Grid executor, **Long** first: start, counters, reduce-only exits, stop, reconcile, restart recovery | Elite | 039B, 039D, 039E, 039F, 039G | 🔴 | Planned |
| [EPIC-039I](incomplete/EPIC-039I_futures_grid_short_and_neutral.md) | Short and Neutral directions on the same executor | Elite | 039H | 🔴 | Planned |
| [EPIC-039L](incomplete/EPIC-039L_protective_stop_mainnet_gate_and_soak.md) | Exchange-side protective stop for a Futures bot, the mainnet gate and the Futures testnet soak | Elite | 039H, `EPIC-026K` | 🔴 | Planned |
| [EPIC-039A](incomplete/EPIC-039A_venue_profile_seam.md) | The venue profile seam: replace every `is SPOT` branch with the profile; "only one" guard; Spot unchanged | Elite | None | 🟡 | Planned |
| [EPIC-039B](incomplete/EPIC-039B_direction_aware_grid_planner.md) | Direction-aware Grid planner and simulator (pure domain); `BaseHandling` becomes `ExposureHandling`; Spot = Long oracle | Elite | 039A | 🟡 | Planned |
| [EPIC-039C](incomplete/EPIC-039C_futures_fake_exchange_matching.md) | Futures fake exchange: LIMIT matching on a price cross, positions, funding, liquidation, user-stream events | Elite | None | 🟡 | Planned |
| [EPIC-039E](incomplete/EPIC-039E_futures_settings_gate_and_readiness.md) | Futures settings gate (leverage, margin type, position mode), brackets, readiness facts, settings-drift halt | Elite | 039A | 🟡 | Planned |
| [EPIC-039G](incomplete/EPIC-039G_futures_costs_funding_and_pnl.md) | Futures costs: commission, funding reader, realized profit; PnL and progress that count them | Elite | 039A, 039C | 🟡 | Planned |
| [EPIC-039J](incomplete/EPIC-039J_futures_ui.md) | UI: Futures venues in the picker, direction/leverage/margin fields, liquidation row, chart and ticks by profile | Elite | 039A, 039E, 039F | 🟡 | Planned |
| [EPIC-039K](incomplete/EPIC-039K_futures_backtest.md) | Futures backtest: Futures candles, funding, liquidation in the simulator | Elite | 039B, 039G | 🟡 | Planned |
| [EPIC-039M](incomplete/EPIC-039M_kind_conformance_for_profiles.md) | A kind declares its supported profiles; a conformance suite every kind passes; proves the seam with the next kind | Elite | 039A, 039H | 🟢 | Planned |

## 5. Phase exit criteria
| Phase | Required outcome | Evidence required to close |
| :--- | :--- | :--- |
| 0 — The seam (039A, 039B) | No `is SPOT` branch outside the profile; the generalised planner reproduces the Spot plan and the Spot simulator result for the same inputs | The guard shown red by re-adding one branch; the Spot-oracle property test; the Spot integration journeys unchanged and green; the `-Full` run green on each head. Not run |
| 1 — The Futures world (039C, 039D, 039E, 039G) | A fake Futures account with positions, funding and liquidation; the exposure book, settings gate and cost model answer from it | Each task's tests red before; a position derived from fills equals the fake's `positionRisk`. Not run |
| 2 — Risk and the executor (039F, 039H) | A Futures Grid (Long) starts, runs, halts and stops on the fake, never leaves a position it cannot account for, and refuses a plan whose liquidation sits inside its range | Integration journeys on the fake exchange; the liquidation guard shown red then green. Not run |
| 3 — All directions and the screen (039I, 039J, 039K) | Short and Neutral behave as the position function of §5 predicts; the screen creates a Futures bot; a backtest includes funding | Property tests; a preview screenshot per state; a backtest with a known funding total. Not run |
| 4 — Safe to risk money (039L, 039M) | A protective stop stands for every Futures position; a 14-day unattended soak on Futures testnet; a second kind gets both profiles by declaration | The owner's soak record; the conformance suite; mainnet Futures stays closed until the owner opens it. Not run |

## 6. Out of scope
- Hedge Mode (long and short positions at once), Multi-Assets mode, Coin-M and delivery contracts, options, and Spot margin.
- Auto-add margin, profit transfer to margin and trailing range (listed in [`DESIGN §11`](DESIGN_2026-10-10_futures_venue_profile.md) as later extension cases).
- The alert module itself (`EPIC-036`), the headless host (`EPIC-038`), the exchange-side stop's general design (`EPIC-026K`): this epic uses them and states what it needs from each.
- A second exchange; the venue profile is the seam for it, and nothing here builds it.
- Any code. This epic is documentation until a child task is started.

## Notes (newest first)
- **2026-10-10** — Epic scaffolded from the owner's request, a code survey (`DESIGN §1`), and research on Futures grid bots (`RESEARCH`). `EPIC-029K` moved to `EPIC-029/cancelled/` as superseded. Documentation only; nothing started; decisions O1–O12 pending.
