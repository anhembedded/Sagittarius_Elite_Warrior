# BOT-236 — A waiting Grid shows the best price it heard, so a wick between two samples is visible

**Status:** ✅ Done (2026-10-27)
**Board:** A Grid waiting on a trigger keeps the lowest (or highest, for a SHORT) price it heard while waiting, the observed kline wick included, and says it beside the last price; it shows the miss of [BUG-276](bug_report/incomplete/BUG-276_a_waiting_grid_with_a_trigger_price_never_sees_a_wick_that_touched_the_trigger.md) and enters nothing.
**Source:** the owner, 2026-10-27, on the BUG-276 design: *"OK duyet"* (translated: "OK, approved"); the coordinator allowed this slice to start alone ([decision D6](epics/EPIC-046_grid_trigger_price/DECISION_2026-10-27_a_triggered_entry_the_bot_cannot_miss.md)).
**Risk:** 🟢 — no order behaviour changes; one optional runtime key is added.
**Complexity:** S — one small watch class, one runtime key, one phrase.
**Epic (optional):** [EPIC-046](epics/EPIC-046_grid_trigger_price/README.md)
**Depends on:** None

---

## 1. Context and problem
The owner's bot `ixr5v8` waited with a trigger while a 15m wick went under it; the screen showed only the last mark (BUG-276). Nothing said whether the price touched the trigger.

## 2. Acceptance criteria
- [x] A bot in `AWAITING_RANGE` keeps the best price heard on its trigger's side (lowest for a bot that wants a lower price, highest for the other), from the mark samples and from the stream's bar extremes the bot observed while listening, and saves it with the record.
- [x] The waiting words name it ("lowest/highest price heard while waiting X") when the plan has a trigger and one was heard; the sentence still ends "nothing is placed until it is".
- [x] A wick from before the bot listened is not kept (`BUG-191`); the entry decision and every order are unchanged.
- [x] A record an earlier build wrote reads as nothing heard.
- [x] A restart or a resume starts from the value the record holds, so the first price after it cannot overwrite an earlier low; a bot with no trigger price keeps and writes nothing (review round 1 of PR #748).

## 3. Design
`GridWaitingBest` (one per bot, on the worker) sits beside `GridPriceReaction`, which hands it every stream tick and mark. It reuses `GridTickExtremes` for the observed wick and `better_is_lower` for the side. The value rides the existing runtime record and `BotProgress` into `TriggerMark.seen_best` and `waiting_text`. A new memory is seeded from the record on its first price, and a bot with no trigger price does nothing. Writes are throttled (`WAITING_BEST_SAVE_SECONDS = 5`); a better price heard in between is held and written on the next price.

## 3a. Reuse
Used `GridTickExtremes`, `better_is_lower`, the `BotProgress` → `PricePosition` → `waiting_text` path every surface shares (the Bots tab, `bot list`/`bot show`, the heartbeat).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/application/kinds/grid/watch/grid_waiting_best.py` | New: the memory of one wait |
| `.../watch/grid_price_reaction.py` | Hands each tick and mark to it |
| `.../domain/grid/grid_runtime.py`, `.../grid_runtime_codec.py` | `waiting_best_price`, optional key |
| `.../contracts/bot_progress.py`, `bot_progress_reader.py`, `grid_ladder.py`, `grid_ladder_texts.py` | Carry it to `TriggerMark.seen_best` and word it |

## 5. Testing
`test_a_waiting_bot_remembers_the_best_price_it_saw.py` (red before: `GridRuntime` had no such field; Spot and futures LONG, SHORT, a wick between samples, a pre-listening wick), `test_grid_ladder_texts.py` (three new), `test_grid_runtime_codec.py` (round trip, old file). Mutation-checked: the side flipped, the wick ignored, the mark path not noted each turn a test red. `tests/unit/architecture` 1128 passed; the bots, alerting application and contract unit tests pass; ruff 0.16.7 check and format clean; mypy shows no error in the touched files.

## 6. Docs touched
`Docs/MODULES/bots/08-concepts.md` (the stored field).

## Implementation notes (written when done)
Slice 1 of BUG-276; the cause stays open until the exchange-held entry (decision D1–D5) is built, which needs the owner's scope confirmation first. The throttle exists so a falling market does not write the record on every tick.
