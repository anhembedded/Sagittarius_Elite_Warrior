# EPIC-029K — A Grid bot runs on Futures with leverage, a liquidation guard and Long, Short or Neutral mode

**Status:** ❌ Cancelled (2026-10-10; superseded by [EPIC-039](../../EPIC-039_futures_venue_profile/README.md))
**Superseded by:** [EPIC-039](../../EPIC-039_futures_venue_profile/README.md). Why: this task scoped Futures as one Grid-only task. The owner's goal (2026-10-10) is that **every** bot kind has a Futures and a Spot side, so the fork is made once in shared ports (a venue profile, an exposure book, a risk guard, a cost model, a settings gate) and the Grid is their first user. The acceptance criteria below are all carried by EPIC-039's children: liquidation guard and the one-ATR stop rule → 039F; ladder orders carry the tag and budget, reduce-only exits → 039D/039H; the fake exchange fills resting Futures LIMIT orders → 039C; restart reconciliation covers the position → 039D/039H. This file is kept as history and is not to be started.

**Status:** 🔵 Backlog — after the fast track; sliced in detail when it starts
**Source:** [`PRO-006`](../../../proposal/PRO-006.md) §4.3 "After the fast track", accepted by the user on 2026-10-03 (*"Oki, duyệt"*).
**Risk:** 🔴 — leverage and liquidation; a stop placed after the liquidation price is worthless.
**Complexity:** L — Futures position model, margin, modes, the liquidation guard, Futures fake-exchange LIMIT matching.
**Epic:** [EPIC-029](../README.md)
**Depends on:** `EPIC-029H`; exchange-side protective stops relate to `EPIC-026K`.

---

## 1. Context and problem
The report (PRO-006 §1.5): on Futures the stop loss must sit before the liquidation price by at least one ATR. Futures adds leverage, one-way positions (`max_positions_per_symbol` semantics) and reduce-only exits.

## 2. Acceptance criteria
- [ ] A Futures Grid plans in Long, Short or Neutral mode with a chosen leverage; the planner computes the estimated liquidation price and refuses a stop loss that is not at least one ATR before it.
- [ ] Ladder orders on Futures carry the bot's tag and budget; exits use reduce-only.
- [ ] The fake exchange fills resting Futures LIMIT orders on a price cross.
- [ ] Restart reconciliation covers the Futures position as well as open orders.

## 3. Design
A second `IBotKind` variant is **not** created: Futures is a venue profile of `GridKind` (spacing and levels are the same); the position model and the liquidation guard are the variant points, listed in `IBotKind`'s docstring since `EPIC-029B`. The full per-file design is written when this task starts, against the tree as it is then.

## 4. Changes, per file
Written when the task starts (the fast track will have changed the files it touches).

## 5. Testing
Written when the task starts; each criterion above maps to a unit or integration test, plus the Testnet tier where an exchange behaviour is involved.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
