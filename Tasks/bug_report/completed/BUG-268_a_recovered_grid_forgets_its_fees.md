# BUG-268 — a Grid that recovers by itself shows only the fees paid since the recovery

- **Reported:** 2026-10-24 (the owner's VPS Futures Testnet bot `nhipxx`, through the coordinating session)
- **Severity:** 🟡 P2 — `Fees paid` on the Bots tab, `bot show` and `bot show --json` reads 0.50 for a run that paid about 2.13, and the realised PnL is overstated by about 0.09; no order or position is affected.
- **Status:** ✅ Fixed (2026-10-24)
- **Board:** A resume (the person's, or the automatic recovery's STARTING → RUNNING) rebuilt the Grid's runtime from a list of fields to keep, which lacked `commissions`, `funding_total` and the protective stops, and took trading's fee-less cost; `resumed_runtime` now replaces only the ladder's own fields and keeps the run's cost while the holding is unchanged.
- **Context:** [SPEC-014 run a grid bot](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md) → `src/modules/bots/` → `application/kinds/grid/start/` (`GridStartSequence.place_ladder`) and `domain/grid/` (`GridRuntime`)
- **Environment:** Headless host on a VPS, Futures Testnet, BNBUSDT Long, capital 200, range 730–750, build of `master-warrior` at or after `EPIC-042`; code read at `d58e705`.

## Reproduction
1. Run a Futures Grid with fills, so its runtime holds `commissions` above zero.
2. Halt it with a transient cause the recovery policy declares (`rate_limited`: the exchange's pause).
3. Let the pause end and the dwell pass: the recovery run proposes and confirms a resume with `condition_cleared`, the bot goes STARTING → RUNNING.
4. Expected: `commissions` unchanged. Actual: `commissions` 0; it grows again from the fills that follow. Every time.

## Symptom
`bot show nhipxx` on 2026-10-24: Realised 21.01, Grid profit 6.81, Cycles 7, Held 2.28 at 738.1099, **Fees paid 0.50**, Funding 0. State file: `commissions 0.50431168`, `realised_total 21.0051855904`, `cost 1682.8905119904`. Journal: 4 opening fills of 0.57 at 734.23 (taker), 17 ladder fills of 0.38, then `RUNNING -> AWAITING_RECOVERY on halt_transient (rate_limited ...)` at 02:19:51, `AWAITING_RECOVERY -> STARTING on condition_cleared` at 02:20:08, `STARTING -> RUNNING on ladder_ready`, then 9 ladder fills.

A replay of those fills (average cost, taker 0.04 % on the opening, maker 0.02 % on the ladder, fees in the cost of buys and in the realised of sells) gives fees **2.131425**; the 9 fills after the recovery alone give 0.504312, the saved `commissions`. The same replay, with the cost replaced at the recovery by the cost trading derives (quote paid, no quote fee: 848.4906 instead of the run's 848.6603 for 1.14 held), gives cost **1682.890512** and realised **21.005186**, the state file's figures to the sixth decimal; without that replacement the run would read cost 1682.971967 and realised 20.916943.

## Root cause
At `d58e705`, `GridStartSequence.place_ladder` (`src/modules/bots/application/kinds/grid/start/grid_start_sequence.py:179`) builds the resumed runtime from `runtime_from_plan` (a fresh runtime at its defaults, `:186`) and copies back a hand-written list of fields (`:187-:203`). `commissions`, `funding_total` and `protective_stops` are not on the list, so each resume sets them to their defaults. It also sets `cost=inventory.cost` (`:191`), trading's derived cost: `inventory_after` (`src/modules/trading/domain/policies/owner_inventory_policy.py:39`) adds the quote paid and never a quote fee, while the run's own cost carries each buy's fee (`grid_books`). On Futures, where fees are paid in USDT, the fees of the held base leave the basis and every later sell books them as profit.

Both the person's Resume from HALTED and the recovery's `condition_cleared` reach `place_ladder` (`grid_resume_sequence.py:319`); a host restart's `RECOVERING` → `RUNNING` does not (it restores the saved runtime), which is why the owner's two earlier resumes kept the total.

The other fields asked about: `unpriced_fees` and `earlier_runs_cost` were on the list and survived. The protective stop's record was dropped; the stop itself is not cancelled by the resume (`tagged_open_orders` excludes stops), and the next supervision adopts it again (`ProtectiveStopBook.adopt`), but between the two a fill of that stop is not recognised as the stop (`GridOffLadderFills._is_protective_stop`). `EPIC-046` added no runtime field: the trigger "latch" is that a bot holding inventory is never flat-resumed into a wait, so nothing of it could be lost here. The gate was green: no test resumed a runtime that held fees, funding or a stop record; no case study, because the fix closes the blind spot for every field at once (below).

## Fix
- `src/modules/bots/domain/grid/grid_resumed_runtime.py` (new) → `resumed_runtime`, `LADDER_FIELDS`: the rule is inverted. The earned runtime is carried whole and only the fields the new ladder owns (levels, owed orders, entry side, halt reason and detail, the stop-in-progress flag) come from it, so a field added to `GridRuntime` later survives a resume by default. The inventory is trading's; its cost is trading's only when the quantity differs from the run's own, because trading's cost holds no quote fee.
- `src/modules/bots/application/kinds/grid/start/grid_start_sequence.py` → `GridStartSequence.place_ladder` calls it instead of copying a list.
- `Docs/MODULES/bots/06-runtime.md`, the recovery attempt's step (3), states what the resume keeps.

**A bot whose total was already lost** cannot be repaired from its state file: the fees of the fills before the resume are no longer in it, and the cost was overwritten. It can be repaired from the exchange's trade history of the run's tagged orders (each Futures trade carries its commission), by the same replay as above; no command does that today, so such a bot shows correctly only from this build on, for the fees and fills that follow. For `nhipxx` the replay of the journal gives `commissions` 2.131425, `cost` 1682.971967 and `realised_total` 20.916943 (`realised_profit`, the cycles, pairs each sell with its buy level and never reads the average cost, so its 6.81 stands); these could be written into the state file by hand with the host stopped, which is the owner's call.

## Regression test
- `tests/integration/modules/bots/test_a_rate_limit_resumes_by_itself_at_the_pauses_end_on_the_fake_exchange.py::test_the_recovered_run_keeps_what_its_fills_paid_and_cost` — failed before the fix with `assert Decimal('0') == Decimal('1.5996720000000000')` (commissions after the recovery against before); passes after.
- `tests/unit/modules/bots/domain/grid/test_grid_resumed_runtime.py` — every `GridRuntime` field the new ladder does not own is carried, and an unchanged holding keeps the cost its fees are in.

## Verification
At the fix commit: the integration test above red without the change to `place_ladder` (stash of that file) and green with it; `tests/unit/modules/bots`, `tests/integration/modules/bots` and `tests/unit/architecture` 7316 passed; `ci-local.ps1 -SkipTests` RESULT: PASS (log grepped, no hit). Positive proof the new mechanism ran: the integration journey's runtime after `STARTING -> RUNNING on ladder_ready` holds the pre-recovery `commissions` 1.599672 and a fresh ladder whose orders share none with the old one.
