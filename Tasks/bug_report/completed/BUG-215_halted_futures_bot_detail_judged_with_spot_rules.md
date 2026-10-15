# BUG-215 — Every Bots-screen refresh raised `WrongVenueFactsError` while a HALTED Futures bot was selected

- **Reported:** 2026-10-15 (owner, desktop app, Futures Testnet Grid "Fu_test_net" in HALTED after "Confirm resume ... refused")
- **Severity:** 🟡 P2. The screen stayed alive, but the bot's detail (facts, verdicts, availability, readiness, chart overlay) did not refresh, and Resume's gate for it was never computed, three times in the owner's session.
- **Status:** ✅ Fixed (2026-10-15)
- **Board:** The Bots screen raised `WrongVenueFactsError` on every detail refresh of a HALTED Futures bot. Cause: `ResumeInputs.profile` defaulted to Spot's and the detail built it without the bot's profile, so the Spot judge got Futures facts. Fix: `profile` is required on `ResumeInputs` and `ReadinessInputs`, and the detail passes the bot's own.
- **Context:** [SPEC-014](../../../Docs/SPEC/SPEC-014_run_a_grid_bot.md), Resume of a halted Grid → `bots` → `ui/bots_screen/` (`bot_detail.py`) over `application/services/readiness/`
- **Environment:** Desktop app, Futures Testnet, `master-warrior` at `f4f85d4`. Reproduced by the unit test below; not run on a live exchange.

## Reproduction
1. A Futures Testnet Grid bot is HALTED.
2. Select it on the Bots screen (any detail refresh: a list answer, a planner answer, the clock).

Expected: the detail is built, Resume is judged with the Futures rules. Actual: the refresh raises. Every time.

## Symptom
```text
App - ERROR - Uncaught UI Exception: an inventory venue was handed Futures facts
  bots_presenter.py:216 _on_read_answered -> _on_list -> detail_effects.py:51 refresh
  -> selected_bot.py:187 detail -> bot_detail.py:157 detail_for -> bot_detail.py:179 _resume_blocked_by
  -> resume_readiness.py:107 assess_resume -> venue_rules.py:56 judge_venue -> venue_rules.py:63 _judge_inventory
WrongVenueFactsError: an inventory venue was handed Futures facts
```

## Root cause
`bot_detail._resume_blocked_by` built `ResumeInputs(config, market, inventory, exchange)` without a profile, and `ResumeInputs.profile` defaulted to `SPOT_PROFILE` (`resume_readiness.py:115`). `assess_resume` then called `judge_venue(SPOT_PROFILE, <FuturesLoaded>, ...)`, which dispatches on the profile's `exposure_kind` to `_judge_inventory` (`venue_rules.py:63`), and that refuses Futures facts by design. The sibling call in the same function, `ReadinessInputs(... profile=bot_profile_of(...))`, passed the profile; only the resume call relied on the default. `ReadinessInputs.profile` (`readiness_assessment.py:128`) had the same silent `= SPOT_PROFILE`; the two production readers (`bot_readiness_reader.py`, `resume_readiness.py`'s reader) happened to pass it. The default was the mechanism: a forgotten argument compiled, type-checked and judged a Futures bot's facts with Spot's rules.

The gate was green because every existing resume test was Spot, and the detail had no test with a HALTED Futures bot. `venue_rules` raising rather than judging wrong facts as empty worked as designed: it is what made the omission visible.

## Fix
- `resume_readiness.py`: `ResumeInputs.profile` has no default.
- `readiness_assessment.py`: `ReadinessInputs.profile` has no default (`field(kw_only=True)`, so the defaulted `exchange` field before it stays as it is and no positional caller moves).
- `bot_detail.py`: one `_profile_of(bot)` (the profile `detail_for` already used for the readiness) now serves the readiness and the resume.
- Existing Spot tests name `SPOT_PROFILE` where they had relied on the default.

Failure boundary on the refresh path, considered and not added: the exception reached Qt's uncaught-exception hook, which logged it as `ERROR` and left the screen alive; that is the report. A `try/except` around `detail()` would hide the next programming error behind an empty detail (`code/errors.md` 6, 7), and the mechanism that raised is now closed at the type level. Not touched: `venue_rules.py` (still raises on mismatched facts).

## Regression test
`tests/unit/modules/bots/ui/bots_screen/test_a_halted_futures_bot_is_judged_by_its_own_venue.py`: the real `detail_for` on a HALTED Futures Testnet snapshot with `FuturesLoaded` facts, no double for the judge. Red before the fix with `WrongVenueFactsError: an inventory venue was handed Futures facts` from `bot_detail.py:182` (both tests); green after. The second test is the positive proof: a Hedge-mode account yields `Resume is blocked: ...`, which only the Futures rules say.

## Verification
Regression tests red before, green after. The bots, trading and architecture unit suites and the commit tier: see the pull request.
