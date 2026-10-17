# EPIC-039L — A Futures position never stands bare: an exchange-side stop, the mainnet gate and the testnet soak

**Status:** 🟡 In progress — C1 merged (#544); C2 merged (#545); C3 (#550) and C4-lite (#551) in review
**Source:** the owner, 2026-10-10; the 2026-10-09 halt ([README §1](../README.md)); [DESIGN §8](../DESIGN_2026-10-10_futures_venue_profile.md); [`EPIC-026K`](../../EPIC-026_road_to_real_money/incomplete/EPIC-026K_exchange_side_protective_stop.md).
**Risk:** 🔴 — a second live order per position; a stop on the wrong side closes nothing, a stop not cancelled on exit opens the opposite position (026K's own warning)
**Complexity:** L — a stop life cycle owned by the bot, adoption on restart, the mainnet gate, a 14-day soak
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (Futures halt and stop), `SPEC-004` is read.
**Design:** [DESIGN §8](../DESIGN_2026-10-10_futures_venue_profile.md) · **Research:** [§4, §8](../RESEARCH_2026-10-10_futures_grid.md) · **Decision:** O7, O8, O12; [`DECISION_2026-10-16`](../DECISION_2026-10-16_futures_protective_stop_minimum.md) (D1–D13, O1–O3, T1–T5) · **Module design:** [`Docs/MODULES/bots/`](../../../../Docs/MODULES/bots/README.md) (`06-runtime.md`, `state-machines.md`)
**Depends on:** [039H](EPIC-039H_futures_grid_long.md); [`EPIC-026K`](../../EPIC-026_road_to_real_money/incomplete/EPIC-026K_exchange_side_protective_stop.md) — **decided (D1, 2026-10-16): 026K has no code, so this task builds the minimum and 026K later adopts the bot's stop mapping.**

---

## 1. Context and problem
A bot that halts, crashes or is closed leaves its exposure where it stands. On Spot that is a holding; on Futures it is a leveraged position whose loss grows with the move. The only protection that survives a dead app is an **order resting on the exchange**. Everything before this task closes the position on halt (O8's default); this task adds the stop so that *leaving* a position becomes acceptable.

### Facts verified on `master-warrior` `076d339` (the first list) and re-checked on `88e283f` by C1 (see §1a)
- Conditional orders go through Binance's Algo Order API in this repo: `trading/adapters/binance/futures_algo_order_mapper.py`, `algo_update_parser.py`, `algo_order_links.py` ("the regular order's `ORDER_TRADE_UPDATE` (its fill) is reported under …"), and the fake: `tests/sanity/fake_exchange/futures_algo_orders.py` (`POST/GET/DELETE /fapi/v1/algoOrder`, `openAlgoOrders`, `allAlgoOrders`, `algoOpenOrders`; `move_price` triggers).
- `OrderType.STOP_MARKET` exists (`trading/contracts/order_type.py:19`); `026K` §1: "while the app is down … the position has no exit at all".
- Binance (opened, RESEARCH §4): `closePosition=true` closes the whole position, only with `STOP_MARKET`/`TAKE_PROFIT_MARKET`, **cannot be combined with `quantity` or `reduceOnly`**, and has Hedge-Mode restrictions; `workingType` `MARK_PRICE`/`CONTRACT_PRICE`; `priceProtect`. The current endpoint and parameters for conditional orders **must be re-read** (RESEARCH §8).
- Bot orders carry the tag `SEW-{tag}-…` (`client_order_id.py`: `tag_of`); the reconcile adopts tagged orders (`grid_reconciler.py`), including, for this task, the stop.
- `countdownCancelAll` (Binance, weight 10): cancels a symbol's open orders when a countdown expires — for the **ladder** only; it would also cancel a resting stop if one is a regular order, so it must not be used with a protective stop on the same symbol unless conditional orders are excluded (verify).
- Venue gating: `TradingVenue.FUTURES_MAINNET` exists and trades like testnet (`EPIC-034` D11); the bots picker offers it since the owner opened it on 2026-10-17 (O2): `CLOSED_VENUES` is gone and no flag replaces it.

## 1a. C1 findings (2026-10-16, `master-warrior` `88e283f`)
Full evidence, the page URLs and the unverified items are in [`DECISION_2026-10-16`](../DECISION_2026-10-16_futures_protective_stop_minimum.md) §1. What changes the plan:
- **There is no 026K mapping to reuse.** 026K is Backlog with no code. The reusable part is the `EPIC-028R` Algo Order mapping, which sends `quantity` + `reduceOnly` + `CONTRACT_PRICE` and has no `closePosition`; `Order` has no `close_position` field. C2 extends that one mapping (D2).
- **`closePosition=true` is documented** (New Algo Order, `POST /fapi/v1/algoOrder`): only `STOP_MARKET`/`TAKE_PROFIT_MARKET`, not with `quantity` or `reduceOnly`, closes the **whole** position of the symbol on its side; `workingType` `MARK_PRICE`/`CONTRACT_PRICE` (default contract price); `priceProtect` default false; `clientAlgoId` unique among open orders. The bot's choice: mark price, `priceProtect` off (D3).
- **Two traps the original task did not name:** (1) `GridHousekeeping.cancel_tagged` and `FuturesTradingClient.cancel_all_orders` cancel algo orders too, so a tagged stop would be cancelled by every ordinary stop unless the ladder reads exclude it (D4); (2) the desk's Emergency Stop cancels everything *before* it closes, so a failed close leaves a bare position (D11).
- **Not answered by the pages (testnet, the owner's):** T1 rejection with no position; T2 survival through a zero position (`EXPIRED` is documented as "canceled by the system" when a user closes all positions on the symbol); T3 a triggered close-all on the side with no position; T4 the "already beyond the market" error; T5 the event order. D8 (re-arm) and D9 (Neutral unprotected until T3) are written so either answer is safe.
- **No offered flag exists** in `bots/` (the task's mention was a plan); the gate is built from `CLOSED_VENUES` (D12).

## 1b. The four pull requests
| PR | Scope | Criteria it closes | Waits on |
| :--- | :--- | :--- | :--- |
| **C1** (documentation only) | This section, the decision record, `Docs/MODULES/bots/` (`06-runtime.md`, `state-machines.md`, `05-building-blocks.md`, diagram), tracking rows | the design of every criterion below | — |
| **C2** the stop life cycle | `Order.close_position`/`working_type`; mapper, parser and fake learn `closePosition`; `protective_stop.py`; runtime and codec fields; place-after-fill with ids saved first (D5); cancel-after-flat (D6); adopt/replace/orphan (D7); re-arm (D8); ladder reads exclude stops through one seam, `tagged_open_orders` = ladder only plus `protective_orders()`, with a guard test (D4); custody of a kept stop and the lease (D13); Neutral second stop behind T3 (D9); events for `EPIC-036B` | criteria 1, 2, 3, 4, 11 (in §2's order) | C1 merged; O3 |
| **C3** the halt policy | `closes_on_halt` asks the exchange at halt time (D10); halts that cannot close; Emergency Stop closes then cancels (D11); `SPEC-014` | criteria 5, 9 | C2 merged; O1 |
| **C4-lite** (revised by O2) | remove `CLOSED_VENUES`; `Docs/OPERATIONS/futures_testnet_soak.md` with T1–T5 as an optional runbook; no port, no state file, no `IShutdownPolicy` (O12 dropped) | criteria 6, 7, 8, 10 | C3 merged; O2 |

## 2. Acceptance criteria
- [x] After the opening fill and before the ladder is declared ready, a **protective stop** (`STOP_MARKET`, `closePosition=true`, `workingType=MARK_PRICE`, tagged with the bot's tag) stands on the exchange at the bot's stop-loss price (and, when the user set it, a take-profit); its ids are saved in the bot's record **before** the next step (the "unsaved and parked" lesson, `grid_task_guard.py`). *(C2: the journey `test_a_stop_stands_before_the_ladder_is_ready`; the take profit stays in-app, A5.)*
- [x] The stop is the **bot's**: Stop/halt/stop-loss cancel it only **after** the position is confirmed flat; a close that fails leaves the stop standing; cancelling it first is a test that must fail. *(C2: `ProtectedCloser` cancels after the close; the mutation that reverses the order was red.)*
- [ ] *(built in C2 behind `NEUTRAL_BOTH_SIDES_VERIFIED = False`, unverified until T3; conditionally deferred: C2 ships Long and Short; Neutral's second stop is built in C2 but counts as protected only once the owner records T3 — D9)* Neutral keeps one stop per side (a long-side and a short-side, each `closePosition`), or the equivalent the official docs support in One-way mode — design recorded after reading the page.
- [x] **Restart:** the reconcile finds the standing stop by its tag and adopts it; a position with **no** stop (the app died between the fill and the stop) is closed or re-protected by a recorded rule, never left; an orphan stop with no position is cancelled (it would open a position on trigger — 026K's warning). *(C2: adopt, re-protect after a crash, cancel an orphan; journeys on the fake.)*
- [ ] *(Deferred out of C3 to a later task, D10 and D13: a halt that can close still closes; see the decision record §7.)* The Futures halt policy (O8): with a stop standing the halt may leave the position; without one it closes. A journey proves each on the fake, including "the stop triggers while the app is down" (the fake's `move_price` then restart: the bot comes back flat and says why).
- [ ] **Settle the event order on testnet** (handed on by 039D): record, from a Futures testnet run, whether `ORDER_TRADE_UPDATE` precedes the `ACCOUNT_UPDATE` of one trade for single fills and for a burst. `POSITION_CHANGED_UNORDERED` (and the 039F guard that halts on it) rests on it; the soak checklist includes a count of divergences the app reported against fills the bot ordered, which must be zero.
- [x] *(Revised by the owner's O2, 2026-10-17: no gate and no soak requirement.)* **Mainnet gate:** Futures mainnet stays closed to bots (the picker lists it greyed out, every create/start/resume refuses it) until (a) this task's journeys are green, (b) the owner records a **14-day unattended soak on Futures testnet** (as `EPIC-026`'s ADR D6 requires for mainnet), (c) the owner opens it. The task adds the soak checklist (what to run, what to read in the logs, what counts as a pass) and does **not** open it. *(C4-lite: the lock is removed; the soak and T1–T5 are the optional runbook `Docs/OPERATIONS/futures_testnet_soak.md`.)*
- [x] *(Answered by the owner, O12 = (a), answer of 2026-10-17 (quoted on PR #551): "(a) Giữ vị thế và lệnh stop trên sàn rồi tắt. Vị thế vẫn được stop bảo vệ, nhưng trong lúc host tắt thì không ai quản lưới lệnh.": the host leaves the position and its protective stop on the exchange, which is `LeaveOrdersResting` today; no `IShutdownPolicy` and no new mechanism are owed. The decision record D12 holds it.)* A headless `run` host (EPIC-038) asks the profile for its stop policy: for a Futures bot without a standing stop "leave orders resting" is refused (O12); the interface is a `IShutdownPolicy` input, recorded here for 038D.
- [x] **Halts that cannot close** *(C3: the words read the exchange; journeys for a stop standing and for one cancelled by hand.)* (handed on by `039H`, review of #490): a switch-off, a rejected key and a rate limit halt a Futures bot without a cancel or a close (the order session is closed or the key refused), so its position stays open on the exchange; `039H` makes the halt's words say so. A standing protective stop is the answer: with it these halts are safe, without it they are the dangerous path; a journey proves a switch-off halt with a stop standing and the words without one.
- [x] **Replace `CLOSED_VENUES`** (`contracts/venue_profile.py`, `closed_venue_refusal`, used by create, change-venue, start, the host's start and resume, and resume): `039H` closes Futures mainnet on every path with that set; this task builds the real gate and removes the set in the same commit that opens the venue. *(Recorded departure, D12: C4 removes the set and opens nothing; the port `IVenueOpening` is closed by default, so the set's job is done from the same commit.)* *(C4-lite: removed, nothing replaces it, per O2.)*
- [x] Alerts: a missing or triggered protective stop publishes the events `EPIC-036B` turns into `STOP_FAILED`/`LIQUIDATION_RISK`. *(C2 publishes `BotProtectiveStopEvent`; mapping it to `STOP_FAILED` is `EPIC-036B`'s.)*

## 3. Design
The decisions are D1–D13 of [`DECISION_2026-10-16`](../DECISION_2026-10-16_futures_protective_stop_minimum.md); the module design is `Docs/MODULES/bots/06-runtime.md` and `state-machines.md` (Planned parts written by C1, made Built by C2–C4). The stop is state owned by the executor with the same persistence discipline as a ladder order (saved before the next step; adopted by tag on reconcile). One close routine (`IExposureCloser`, 039H) serves every exit; the stop is the exchange's copy of that same exit for when the app is gone. Extend the existing Algo Order mapping rather than build a parallel one (`EPIC-037`: one place; D2). *(Superseded by O2: there is no gate.)* The mainnet gate is a *configuration the owner flips*, never a code default.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/application/services/protective_stop.py` (new) | place, record, cancel-after-flat, adopt, orphan cleanup |
| `bots/application/kinds/grid/recovery/grid_reconciler.py` (via the exposure-check seam, 039H) | adopt/orphan rules |
| `bots/domain/grid/grid_runtime.py` | the stop's ids on the runtime and in the codec (`grid_runtime_codec.py`, version-safe) |
| `trading/contracts/order.py`, `trading/adapters/binance/futures_algo_order_mapper.py`, `algo_update_parser.py` | `close_position`, `working_type`; `closePosition` params without `quantity`/`reduceOnly` (C2) |
| `tests/sanity/fake_exchange/futures_algo_orders.py` | `closePosition` semantics, `EXPIRED` on a flat symbol, a close-all trigger sized by the position (C2) |
| `trading/application/session/emergency_stop/handler.py` | close the positions, then cancel the algo orders (C3) |
| `bots/contracts/venue_profile.py` | remove `CLOSED_VENUES` (C4-lite; no port replaces it, O2) |
| `Docs/OPERATIONS/…` or the task notes | the soak checklist |

## 5. Testing
Tier: unit; integration on the Futures fake (algo orders, `move_price`); the soak is the owner's.
- `test_the_stop_stands_before_the_ladder_is_ready_and_its_ids_are_saved_first`
- `test_stop_cancels_the_protective_stop_only_after_flat` (mutation: reverse the order → red)
- `test_a_restart_adopts_the_standing_stop` · `test_a_position_without_a_stop_after_a_crash_is_re_protected_or_closed` · `test_an_orphan_stop_is_cancelled`
- Custody (D13, one test each): `test_a_stop_with_keep_stands_under_custody_and_the_symbol_stays_claimed` · `test_a_dust_remainder_cancels_the_stop` · `test_a_foreign_position_cancels_the_bots_stop` · `test_a_new_bot_on_a_symbol_in_custody_is_refused`
- `test_no_ladder_read_sees_a_close_position_order` (the guard of D4's seam: mutation, let `tagged_open_orders` return a stop → red; and `GridStopSequence` confirms with a stop kept)
- `test_a_triggered_stop_is_decided_from_the_algo_status_not_from_fill_attribution` · `test_a_stop_is_not_re_placed_while_flat`
- `test_the_stop_triggers_while_the_app_is_down_and_the_bot_returns_flat`
- `test_a_halt_with_a_stop_standing_leaves_the_position_and_without_one_closes_it`
- `test_futures_mainnet_is_not_offered_until_the_owner_opens_it`
C2: the tests above exist except the custody ones (D13 moved to C3, decision §8 A1) and the halt and gate ones (C3, C4). Futures testnet: the owner's, recorded in this task (T1–T5 of the decision record).

## Pitfalls
- A conditional stop that triggers **after** the bot already closed opens the opposite position: cancel-after-flat and orphan cleanup are the two halves of one rule.
- `closePosition=true` stops are not combined with `quantity`/`reduceOnly`; mixing them is a rejected order.
- Persist before acting (a stop placed and not saved is an orphan after a crash).
- Never test on a real exchange from CI; the soak is the owner's.

## Implementation notes (written when done)
C3: `ITradingClient.cancel_regular_orders` / `cancel_conditional_orders` (Futures: `futures_cancel_all_open_orders` vs `futures_cancel_all_algo_open_orders`; Spot: the second is empty); the Futures Emergency Stop steps in `trading/application/session/emergency_stop/futures_stop_steps.py`; `EmergencyStopResult.conditional_orders_cancelled`; `IExposureProtection.describe_stop` feeding `GridParking.left_open_words`.
C1 (design) is documentation only: no code, no test. C2 (the stop life cycle) is built on the fake: `closePosition` through the one Algo Order mapping, the bot's `ProtectiveStop` record and machine, `ProtectiveStopService` / `ProtectiveStopBook` / `ProtectedCloser` behind the port `IExposureProtection`, the ladder-versus-stop seam in `BotAccountReads`, and the fake exchange's `ALGO_UPDATE` and close-all semantics. Departures and findings: decision record §8. C3 is built in #550 (see Resume); C4 is revised by the owner's O2 (#551).

## Resume
PR #544 review (round 1): F1/F2 answered by D13 and D4's seam; F3–F9 by D5, D6, D8, D9, D11, §3.1/§3.2, criterion notes and the diagram. K5: the terms *protective stop*, *unprotected* and *custody* go to `Docs/VOCABULARY` in C2, with the symbols that name them.
C1 merged (#544), C2 merged (#545). The owner answered O1–O3 on 2026-10-17 (quoted in the decision record §6). C3 is built in its pull request: D11 (Emergency Stop order) and criterion 9 (the halt's words). Deferred out of C3, with the reason in the decision record §7: D10 (a halt that can close still closes) and D13 (custody). C4 is revised by O2: the Futures mainnet lock is removed outright, no port and no state file; the soak and T1–T5 stay a runbook the owner may follow. The owner's T1–T5 testnet runs are recorded in the decision record §6 and may land at any time; C2 must not rely on T3 for Long/Short.

## Docs touched
C3: `Docs/MODULES/bots/` `06-runtime.md` (Emergency Stop order, the halt's words, Planned narrowed), `05-building-blocks.md`, `diagrams/06-emergency-stop.puml`; the decision record §6–§7.
C2: `Docs/MODULES/bots/` `03-context.md`, `05-building-blocks.md`, `06-runtime.md`, `08-concepts.md`, `state-machines.md` (generated protective-stop table), `README.md`, `diagrams/06-protective-stop.puml`; `Docs/VOCABULARY/README.md` (protective stop, unprotected); the decision record §7–§8.
