# EPIC-029I — The desks trade manually only, show which bot holds a symbol, and offer a takeover

**Status:** 🔵 Backlog — after the fast track; sliced in detail when it starts
**Source:** [`PRO-006`](../../../proposal/PRO-006.md) §4.3 "After the fast track", accepted by the user on 2026-10-03 (*"Oki, duyệt"*).
**Risk:** 🟡 — removes the strategy card from both desks; the takeover stops a bot and hands its position to the user.
**Complexity:** M — desk view change, a read-only badge, the lease refusal naming its holder, a takeover dialog, SPEC-010.
**Epic:** [EPIC-029](../README.md)
**Depends on:** `EPIC-029H` (the fast track is done).

---

## 1. Context and problem
The user chose on 2026-10-03 that the desks become manual only, with a read-only bot badge and a takeover ("Chặn, có nút tiếp quản" — refuse, with a takeover button). It was kept off the fast track because a single Grid bot does not need it: the lease already refuses a manual order on the bot's symbol (`execute_order/handler.py:208`). Today the refusal does not say who holds the symbol, and the holder cannot be queried through a published port (`trading/contracts/i_trading_session.py:62-105`).

## 2. Acceptance criteria
- [ ] Both desks no longer show the strategy card (`desk_view.py:100-103,135-152`); the Dev Board keeps it as a developer tool.
- [ ] A desk shows a read-only badge for a bot running on its venue: name, symbol, state, and a link that opens the Bots tab on that bot.
- [ ] A manual order refused by `SYMBOL_LEASED` names the holding bot; the refusal offers "Stop bot to trade manually", whose dialog states what happens to resting orders and inventory before it acts.
- [ ] The lease holder becomes readable through a published query (owner id → bot read model resolved in `bots`), without exposing trading's internal state.
- [ ] `SPEC-010` is written as "run a bot" (the reserved slot, `Docs/SPEC/README.md`), replacing "arm a strategy".

## 3. Design
A `lease_holder(symbol)` query on `ITradingSession` returns the owner id only; `bots` maps a bot owner id to its read model. The desk never imports `bots`: the badge data arrives through a trading-published read port that `bots` implements (the pattern of `IVenueStrategyControls`, `EPIC-028K`). The full per-file design is written when this task starts, against the tree as it is then.

## 4. Changes, per file
Written when the task starts (the fast track will have changed the files it touches).

## 5. Testing
Written when the task starts; each criterion above maps to a unit or integration test, plus the Testnet tier where an exchange behaviour is involved.

## Implementation notes (written when done)

## Resume (optional; while unfinished)
