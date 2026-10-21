# EPIC-044B — A Grid started away from its range waits in `AWAITING_RANGE` and lays its ladder when the price enters

**Status:** 🔵 Backlog
**Source:** the owner, 2026-10-21, through the coordinating session (quoted once in the epic README: *"trường hợp giá out range, thì bot vẫn start, nhưng chờ giá vào trong range thì bot mới bắt đầu init lệnh"* — if the price is out of the range the bot still starts but only begins laying orders once the price is inside).
**Risk:** 🔴 — it changes what a real-money bot does at Start, in every direction and on both markets, and adds a lifecycle state.
**Complexity:** L — the lifecycle table, the start path, the entry watch, the checks, the restore row and the red-before tests of every direction × side.
**Epic (optional):** [EPIC-044](../README.md)
**SPEC (optional):** [SPEC-014](../../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)
**Depends on:** [EPIC-044A](EPIC-044A_the_decision_record.md) accepted

---

## 1. Context and problem
The ADR's D1–D9 and D12. Established on `849d973`: five behaviours depending on direction and side, one of which (SHORT above the range) market-shorts the whole capital while the check says otherwise.

## 2. Acceptance criteria
- [ ] **Red first.** On `849d973` a test shows a SHORT started above its range plans a market short of the BUY levels' quantity and that its verdict says "BUY orders only"; the PR says so plainly.
- [ ] For each of LONG, SHORT, NEUTRAL × price below and above the range, on Spot (LONG) and Futures: Start leaves the bot `AWAITING_RANGE` with **zero orders** placed and no opening trade; a later in-range tick lays the ladder the plan gives at the entry price, including the opening buy or short.
- [ ] The entry decision uses the mark on Futures and the last trade on Spot; the bounds are inside; a price that is back outside when the plan's price is re-read lays nothing.
- [ ] `PRICE_BELOW_RANGE` / `PRICE_ABOVE_RANGE` are informational (`OK`), direction-free, say "starts waiting for the price to enter X–Y (now Z)", and block nothing; the rest of the plan is judged at the nearest bound.
- [ ] A restart while waiting leaves the bot `RECOVERING`, the reconcile returns it to `AWAITING_RANGE`, and nothing is laid; an unknown tagged order halts it.
- [ ] Stop while waiting cancels nothing and ends in `STOPPED`; the lease and budget are released.
- [ ] Stop loss and take profit (and the range-exit close) do nothing while waiting, whatever the price.
- [ ] A refusal at entry halts with `ENTRY_REFUSED` and its detail (a REFUSED verdict, a budget refusal, an order below the minimum); a transient cause keeps waiting and says so once.
- [ ] Mainnet and testnet behave the same (the same test over both venues).
- [ ] Every hand-written state set classifies `AWAITING_RANGE` (ADR §2.4), held by the existing every-set-classifies-every-state guard.
- [ ] Log lines of ADR D12 seen through the real logging configuration; `render_log_templates.py --write` run.

## 3. Design
The ADR §2. A new `GridRangeEntry` collaborator in `application/kinds/grid/watch/` decides on each tick; the executor posts the entry as the same `STARTING` start sequence that lays every ladder.

## 3a. Reuse
`range_position` (the one definition of inside); `AWAITING_RECOVERY`'s pattern; `GridStartSequence`, `GridHousekeeping.register`, `GridStopper`, `BotRestoreService`/`GridReconciler`; `halt_with`/`fail_with`. Not used: a new bus event (the state change carries the alert).

## 4. Changes, per file
Decided when read at implementation time; expected: `bot_lifecycle_fsm_matrix.py`, `grid_range_checks.py`, `grid_constraints.py`, `grid_executor.py`, `grid_price_reaction.py`, a new `grid_range_entry.py`, `grid_runtime.py` (`ENTRY_REFUSED`), the state sets of ADR §2.4, `Docs/MODULES/bots/state-machines.md`, `SPEC-014`, `Docs/VOCABULARY/README.md`.

## 5. Testing
The criteria above, each red before and green after, unit tier plus an integration journey over the real executor and the fake exchange; mutation-checked (flip the bound inclusion, swap the mark and the last, remove the zero-order guarantee).

## 6. Docs touched
`Docs/MODULES/bots/state-machines.md` (the new state and rows), `Docs/MODULES/bots/06-runtime.md` (the entry sequence), `Docs/SPEC/SPEC-014_run_a_grid_bot.md`, `Docs/VOCABULARY/README.md` (*Awaiting range*, *Range position*).
