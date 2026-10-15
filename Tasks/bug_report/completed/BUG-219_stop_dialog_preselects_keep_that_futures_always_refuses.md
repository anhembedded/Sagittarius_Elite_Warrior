# BUG-219 — Stopping a Futures bot offers, and preselects, "Keep the base", which Stop always refuses

- **Reported:** 2026-10-15 (owner, chat, with a screenshot)
- **Severity:** 🟡 P2 — the owner concluded a HALTED Futures bot holding a 0.596 ETH long cannot be stopped at all; the working choice (close) was one click away but not offered as the default.
- **Status:** ✅ Fixed (2026-10-15)
- **Board:** Stop on a Futures bot preselected "Keep the base" and then refused it in an error box. Cause: the dialog and the Stop use case each decided what a venue may keep, and only the use case asked the venue profile. Fix: `keep_on_stop_closed_reason` on the venue profile is read by both; the dialog disables Keep with its reason and preselects the close, worded for a position.
- **Context:** Bots tab → Stop bot → `src/modules/bots/ui/bots_screen/` (`ui/`), `src/modules/bots/application/use_cases/stop_bot/` (`application/`), `src/modules/bots/contracts/venue_profile.py`
- **Environment:** Futures Testnet bot "Fu_test_net", HALTED, long 0.596 ETH; master-warrior at 5ac84b3.

## Reproduction
1. Hold a Futures Testnet grid bot (any state that offers Stop) with an open position.
2. Press Stop in the Bots toolbar; the dialog preselects "Keep the base in the account".
3. Press "Stop bot". Expected: the bot stops (closing the position). Actual: error box "Stop Fu_test_net: refused. Futures positions are not kept when a bot stops: this app places no stop on the exchange yet ... Stop and close the position."

Frequency: every Stop of a bot on a position venue.

## Symptom
Owner screenshot 2026-10-15 (error box text above). Expected instead: a choice that cannot run is caught before it is offered, not after.

## Root cause
`stop_bot_dialog.py` always offers Keep (preselected) and "Sell the base at market" in Spot wording, while `stop_bot/handler.py::_keep_refusal` refuses KEEP for any venue whose profile `exposure_kind` is POSITION. Two places decide the same question and only one of them asks the venue profile. Not a gate escape: no net compared the dialog's offer with the handler's refusal.

## Fix
- `contracts/venue_profile.py`: `keep_on_stop_closed_reason(profile)` (the one question) and the profile's `held_word` / `close_at_market_label`.
- `stop_bot/handler.py`: `_keep_refusal` asks that function; the refusal stays as the backstop.
- `ui/bots_screen/stop_bot_dialog.py`: Keep disabled with its reason beside it, close preselected and worded "Close the position at market", question says "position"; Spot unchanged.

## Regression test
`tests/unit/modules/bots/ui/bots_screen/test_stop_dialog_offers_only_what_stop_accepts.py` - Futures dialog (Keep disabled, close preselected, position wording), Spot unchanged, and dialog/handler agreement for every `TradingVenue`. Five of its tests failed before the fix (Keep enabled and preselected while the handler refused it); all pass after.

## Verification
Regression file and `tests/unit/modules/bots/ui/bots_screen` plus `test_stop_keeps_no_position.py` green; commit tier and architecture guards run before the commit. Before/after sequences: see the pull request (`fix-bug-rule.md` §6.1 - not applicable, one function and one dialog).
