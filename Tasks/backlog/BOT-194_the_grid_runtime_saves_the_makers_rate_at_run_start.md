# BOT-194 — The Grid runtime saves the account's maker rate when a run starts, so the net after fees shows

**Status:** 🔵 Backlog
**Priority:** P2
**Board:** Save the maker fee rate the start sequence reads in the grid runtime (one optional field), so the Bots tab and `bot show` can fill in the net step and the profit per cycle after fees, labelled "rate recorded at run start".
**Source:** Found while delivering [BOT-193](BOT-193_a_grid_bot_shows_its_ladder_summary_and_price_position.md): the rate is read from the exchange and not saved, so a read-only copy cannot give the net. 🤖 Agent decision delegated by the user, 2026-10-19: the owner answered "A,B gì thế, tự quyết theo hiến pháp đi" ("decide yourself by the Constitution") and the coordinator chose A; it is not a §7 default decision (the state file is user data) and the owner may veto. The Constitution check is in [PRO-016](../proposal/PRO-016.md) §6.
**Risk:** 🟡 — touches the start sequence and the runtime codec; no order or bot behaviour changes, and an old file without the field must still load.
**Complexity:** S — one optional field on `GridRuntime`, its codec lines, two readers.
**Depends on:** BOT-193 (both pull requests) merged.

---

## 1. Context and problem
`GridRuntime` holds `start_price`, `mark_price` and the commissions paid, not the rate. `bots/contracts/grid_ladder.py` → `grid_ladder_of` takes `maker_fee` and both consumers pass `None`, so the net columns are blank.

## 2. Acceptance criteria
- [ ] A new run writes the maker rate its start read into the runtime, and a resume keeps it (as `start_price` is kept).
- [ ] A file without the field loads and shows "before fees"; the field round-trips through the codec.
- [ ] The Bots tab and `bot show` fill the net step and the profit per cycle after fees from it, labelled "rate recorded at run start".
- [ ] A journey on the fake exchange proves the field is written at start and read by both consumers.
- [ ] No order, bot behaviour or alert changes.

## 3. Design
See PRO-016 §6, "Constitution check". The consumers pass `GridRuntime.maker_fee` through `BotProgress` into `grid_ladder_of`; the wording says "recorded at run start".

## 3a. Reuse
`grid_ladder_of(maker_fee=…)`, `grid_ladder_texts`, the runtime codec pattern of `start_price`. Not used: a second fee source.

## 4. Changes, per file
To be written when started: `domain/grid/grid_runtime.py`, `application/kinds/grid/grid_runtime_codec.py`, `.../start/grid_start_sequence.py`, `contracts/bot_progress.py`, `.../bot_progress_reader.py`, the two consumers, their tests and the docs of BOT-193.

## 5. Testing
Unit (codec, old file, wording) and one fake-exchange journey.

## 6. Docs touched
`Docs/MODULES/bots/` (the runtime's stored fields), the headless runbook's ladder section.

## Implementation notes (written when done)
_Not started._
