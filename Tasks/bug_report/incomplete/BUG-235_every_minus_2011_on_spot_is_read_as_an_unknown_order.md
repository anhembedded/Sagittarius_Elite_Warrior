# BUG-235 — Every Binance `-2011` is read as "unknown order", though on Spot it is the generic cancel-rejected code

- **Reported:** 2026-10-19 (the reviewer of #589, from the translator's own comment and Binance's documented messages; relayed by the coordinator)
- **Severity:** 🟡 P2. On Spot a refused cancel of a live ladder order may be read as "the order is gone", and since #579 the ladder's housekeeping trusts that without reading the orders again. Not seen on an exchange; the cost is a live order the bot no longer tracks.
- **Status:** Open
- **Board:** `binance_error_translator.py` maps every `-2011` to `UNKNOWN_ORDER`, but on Spot `-2011` is the generic CANCEL_REJECTED ("Unknown order sent.", "Market is closed.", "This action is disabled on this account."), so a refused cancel can be dropped as gone.
- **Context:** `trading` → `src/modules/trading/adapters/binance/binance_error_translator.py`, consumed by `bots` (`BotOrderGateway.cancel`, `GridHousekeeping._ended_meanwhile`)
- **Environment:** by reading at `a344b25`; Spot answers not captured. Futures' `-2011` is "Unknown order sent." in the answers seen so far.

## Reproduction
Not yet reproduced. A Spot cancel answered `-2011` with a message other than "Unknown order sent." should keep the order tracked (cancel refused), not end it.

## Symptom
Not observed. The translator's table maps `-2011` and `-2013` to `UNKNOWN_ORDER` and its own comment says the mapping is unverified against a live answer.

## Root cause
Not yet established by a run. From reading: `_UNAMBIGUOUS_CODE_TO_REASON` treats `-2011` as one thing; `-1013`, the generic filter failure, is narrowed by message in the same file (`_GENERIC_FILTER_FAILURE_CODE`). `-2011` was not given the same treatment.

## Fix
Not started. Narrow `-2011` by message, as `-1013` is: "Unknown order sent." (and the Futures answer) is `UNKNOWN_ORDER`; any other `-2011` message is a cancel refusal of its own kind, raised and read again by the caller.

## Regression test
Not written: a translator unit test with a Spot `-2011` "Market is closed." answer, and a gateway test that such a cancel is not `GONE`.

## Verification
Not run.

## Suggested next steps
Capture one real Spot `-2011` message of each kind before narrowing (the translator's comment asks for that), or narrow conservatively to the exact "Unknown order sent." text.
