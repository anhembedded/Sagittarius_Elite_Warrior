# EPIC-039L — A Futures position never stands bare: an exchange-side stop, the mainnet gate and the testnet soak

**Status:** 🔵 Planned — not started
**Source:** the owner, 2026-10-10; the 2026-10-09 halt ([README §1](../README.md)); [DESIGN §8](../DESIGN_2026-10-10_futures_venue_profile.md); [`EPIC-026K`](../../EPIC-026_road_to_real_money/incomplete/EPIC-026K_exchange_side_protective_stop.md).
**Risk:** 🔴 — a second live order per position; a stop on the wrong side closes nothing, a stop not cancelled on exit opens the opposite position (026K's own warning)
**Complexity:** L — a stop life cycle owned by the bot, adoption on restart, the mainnet gate, a 14-day soak
**Epic:** [EPIC-039](../README.md)
**SPEC:** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) (Futures halt and stop), `SPEC-004` is read.
**Design:** [DESIGN §8](../DESIGN_2026-10-10_futures_venue_profile.md) · **Research:** [§4, §8](../RESEARCH_2026-10-10_futures_grid.md) · **Decision:** O7, O8, O12
**Depends on:** [039H](EPIC-039H_futures_grid_long.md); [`EPIC-026K`](../../EPIC-026_road_to_real_money/incomplete/EPIC-026K_exchange_side_protective_stop.md) (reuse its order mapping; if 026K has not landed, this task builds the minimum and 026K later adopts it — decide with the owner).

---

## 1. Context and problem
A bot that halts, crashes or is closed leaves its exposure where it stands. On Spot that is a holding; on Futures it is a leveraged position whose loss grows with the move. The only protection that survives a dead app is an **order resting on the exchange**. Everything before this task closes the position on halt (O8's default); this task adds the stop so that *leaving* a position becomes acceptable.

### Facts verified on `master-warrior` `076d339`
- Conditional orders go through Binance's Algo Order API in this repo: `trading/adapters/binance/futures_algo_order_mapper.py`, `algo_update_parser.py`, `algo_order_links.py` ("the regular order's `ORDER_TRADE_UPDATE` (its fill) is reported under …"), and the fake: `tests/sanity/fake_exchange/futures_algo_orders.py` (`POST/GET/DELETE /fapi/v1/algoOrder`, `openAlgoOrders`, `allAlgoOrders`, `algoOpenOrders`; `move_price` triggers).
- `OrderType.STOP_MARKET` exists (`trading/contracts/order_type.py:19`); `026K` §1: "while the app is down … the position has no exit at all".
- Binance (opened, RESEARCH §4): `closePosition=true` closes the whole position, only with `STOP_MARKET`/`TAKE_PROFIT_MARKET`, **cannot be combined with `quantity` or `reduceOnly`**, and has Hedge-Mode restrictions; `workingType` `MARK_PRICE`/`CONTRACT_PRICE`; `priceProtect`. The current endpoint and parameters for conditional orders **must be re-read** (RESEARCH §8).
- Bot orders carry the tag `SEW-{tag}-…` (`client_order_id.py`: `tag_of`); the reconcile adopts tagged orders (`grid_reconciler.py`), including, for this task, the stop.
- `countdownCancelAll` (Binance, weight 10): cancels a symbol's open orders when a countdown expires — for the **ladder** only; it would also cancel a resting stop if one is a regular order, so it must not be used with a protective stop on the same symbol unless conditional orders are excluded (verify).
- Venue gating: `TradingVenue.FUTURES_MAINNET` exists and trades like testnet (`EPIC-034` D11); the bots picker offers it only when the owner opens it (039J's `offered` flag).

## 2. Acceptance criteria
- [ ] After the opening fill and before the ladder is declared ready, a **protective stop** (`STOP_MARKET`, `closePosition=true`, `workingType=MARK_PRICE`, tagged with the bot's tag) stands on the exchange at the bot's stop-loss price (and, when the user set it, a take-profit); its ids are saved in the bot's record **before** the next step (the "unsaved and parked" lesson, `grid_task_guard.py`).
- [ ] The stop is the **bot's**: Stop/halt/stop-loss cancel it only **after** the position is confirmed flat; a close that fails leaves the stop standing; cancelling it first is a test that must fail.
- [ ] Neutral keeps one stop per side (a long-side and a short-side, each `closePosition`), or the equivalent the official docs support in One-way mode — design recorded after reading the page.
- [ ] **Restart:** the reconcile finds the standing stop by its tag and adopts it; a position with **no** stop (the app died between the fill and the stop) is closed or re-protected by a recorded rule, never left; an orphan stop with no position is cancelled (it would open a position on trigger — 026K's warning).
- [ ] The Futures halt policy (O8): with a stop standing the halt may leave the position; without one it closes. A journey proves each on the fake, including "the stop triggers while the app is down" (the fake's `move_price` then restart: the bot comes back flat and says why).
- [ ] **Mainnet gate:** Futures mainnet stays out of the bot venue picker (`offered=False`) until (a) this task's journeys are green, (b) the owner records a **14-day unattended soak on Futures testnet** (as `EPIC-026`'s ADR D6 requires for mainnet), (c) the owner opens it. The task adds the soak checklist (what to run, what to read in the logs, what counts as a pass) and does **not** open it.
- [ ] A headless `run` host (EPIC-038) asks the profile for its stop policy: for a Futures bot without a standing stop "leave orders resting" is refused (O12); the interface is a `IShutdownPolicy` input, recorded here for 038D.
- [ ] Alerts: a missing or triggered protective stop publishes the events `EPIC-036B` turns into `STOP_FAILED`/`LIQUIDATION_RISK`.

## 3. Design
The stop is state owned by the executor with the same persistence discipline as a ladder order (saved before the next step; adopted by tag on reconcile). One close routine (`IExposureCloser`, 039H) serves every exit; the stop is the exchange's copy of that same exit for when the app is gone. Reuse `026K`'s mapping rather than a parallel one (`EPIC-037`: one place). The mainnet gate is a *configuration the owner flips*, never a code default.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `bots/application/services/protective_stop.py` (new) | place, record, cancel-after-flat, adopt, orphan cleanup |
| `bots/application/services/grid_reconciler.py` (via the exposure-check seam, 039H) | adopt/orphan rules |
| `bots/domain/grid/grid_runtime.py` | the stop's ids on the runtime and in the codec (`grid_runtime_codec.py`, version-safe) |
| `trading/…` (only if 026K's mapping is not enough) | the bot-owned stop through `IOrderSubmission` |
| `Docs/OPERATIONS/…` or the task notes | the soak checklist |

## 5. Testing
Tier: unit; integration on the Futures fake (algo orders, `move_price`); the soak is the owner's.
- `test_the_stop_stands_before_the_ladder_is_ready_and_its_ids_are_saved_first`
- `test_stop_cancels_the_protective_stop_only_after_flat` (mutation: reverse the order → red)
- `test_a_restart_adopts_the_standing_stop` · `test_a_position_without_a_stop_after_a_crash_is_re_protected_or_closed` · `test_an_orphan_stop_is_cancelled`
- `test_the_stop_triggers_while_the_app_is_down_and_the_bot_returns_flat`
- `test_a_halt_with_a_stop_standing_leaves_the_position_and_without_one_closes_it`
- `test_futures_mainnet_is_not_offered_until_the_owner_opens_it`
Not run yet. Futures testnet: the owner's, recorded in this task.

## Pitfalls
- A conditional stop that triggers **after** the bot already closed opens the opposite position: cancel-after-flat and orphan cleanup are the two halves of one rule.
- `closePosition=true` stops are not combined with `quantity`/`reduceOnly`; mixing them is a rejected order.
- Persist before acting (a stop placed and not saved is an orphan after a crash).
- Never test on a real exchange from CI; the soak is the owner's.

## Implementation notes (written when done)
Not started.

## Resume
Not started. First action: read Binance's conditional/algo order page and the state of `EPIC-026K`; record both here and ask the owner whether this task builds the minimum or waits for 026K.
