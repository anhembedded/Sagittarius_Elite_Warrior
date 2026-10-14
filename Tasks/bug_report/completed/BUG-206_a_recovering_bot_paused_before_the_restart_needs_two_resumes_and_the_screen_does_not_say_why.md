# BUG-206 — A RECOVERING bot that was PAUSED before the restart needs two Resume presses, and the screen does not say why

- **Reported:** 2026-10-14 (owner, real-money Spot Mainnet bot `ke95g7`; relayed by the coordinator session)
- **Severity:** 🟡 P2 — no money is at risk, but the screen promises "continue" and the first Resume leaves the bot paused, so the owner cannot tell whether the press worked
- **Status:** ✅ Fixed (2026-10-14)
- **Board:** The state line of a Recovering bot always promised "continue", and the dropped Resume of a restored PAUSED bot was only logged; fixed by carrying the bot's `recovering_from` to the screen so the line names the state the reconcile returns to, and by recording the reason `restored_paused` when the reconcile puts the bot back to PAUSED, which the screen shows until the next Resume.
- **Context:** Bots → restart rule and Resume ([SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md)) → `src/modules/bots/` → `contracts/bot_snapshot.py`, `application/services/grid_reconciler.py`, `ui/bots_screen/bot_facts.py`
- **Environment:** Desktop app on `master-warrior` after `BUG-204` (`1c4d5fc`), Spot Mainnet. Reproduced in unit tests only; nothing was placed, tested or simulated against Binance mainnet.

## Reproduction
1. Pause a running bot, close the app, start the app: the bot is RECOVERING, `recovering_from` PAUSED.
2. Read the state line, press Resume once.
3. Expected: the line says the bot will come back PAUSED; after the press, that it is PAUSED and needs Resume. Actual: "Recovering — waiting for you: press Resume to open the order session and continue", then (log only) `resume from RECOVERING dropped, the bot is PAUSED`.

## Symptom
```
Bot ke95g7: reconcile SEW-ke95g7-2bef1e2ad9 executed 0.00230000 since
Bot ke95g7: RECOVERING -> PAUSED on reconcile_ok
Bot ke95g7: resume from RECOVERING dropped, the bot is PAUSED [recovering-resume]
```
A second press gave PAUSED -> RUNNING. Returning to the prior state is intended (`BUG-204`: a queued Resume never unpauses a bot the owner paused) and is unchanged.

## Root cause
The screen never knew the prior state. `Bot.lifecycle.recovering_from` (`domain/bot.py`) holds it, but `BotSnapshot.of` did not copy it, so `_state_line` (`ui/bots_screen/bot_facts.py`) wrote one sentence for every prior state, "continue". After the reconcile, `GridReconciler.run` (`grid_reconciler.py`) cleared the reason (`RECOVERY_READ` replaced by nothing), so a restored PAUSED bot looked like any other paused bot; only the executor's `[recovering-resume]` log line (`grid_executor.py`, `_run_resume`) recorded the drop.

## Fix
- `contracts/bot_snapshot.py`: `BotSnapshot.recovering_from`, copied from the bot — the prior state is data, the UI derives nothing.
- `ui/bots_screen/bot_facts.py`: a RECOVERING bot that was PAUSED says "it was Paused before the restart. Resume … returns it to Paused; press Resume again to run"; the Running wording is unchanged.
- `domain/grid/grid_runtime.py`, `application/services/grid_reconciler.py`, `bot_run_state.py`: a reconcile that returns a PAUSED-before bot to PAUSED records `GridReason.RESTORED_PAUSED` with the text "reconciled with the exchange after the restart; it stays paused as you left it. Press Resume to run"; the next Resume clears it.

## Regression test
- `tests/unit/modules/bots/ui/test_a_recovering_bot_names_the_state_it_returns_to.py` — the state line for each prior state, the snapshot's data, and the post-return line. Red before the fix: the PAUSED-prior line was "…press Resume to open the order session and continue".
- `tests/unit/modules/bots/application/services/test_grid_resume_from_recovering.py::test_a_bot_paused_before_the_restart_comes_back_paused_and_says_so` — red before the fix with `assert None is GridReason.RESTORED_PAUSED`; the second Resume runs the bot and clears the note.

## Verification
- Both new tests red against the pre-fix behaviour, green after; `pytest tests/unit/modules/bots`: 3183 passed. Commit tier: see the PR body.
- Not verified: a real-money run.

## Docs touched
`Docs/SPEC/SPEC-014_run_a_grid_bot.md` (the state line and the return to Paused), `Docs/MODULES/bots.md` §4.
