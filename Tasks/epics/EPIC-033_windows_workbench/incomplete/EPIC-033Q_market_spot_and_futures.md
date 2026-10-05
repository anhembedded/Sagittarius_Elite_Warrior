# EPIC-033Q — The Market mode shows Spot or Futures candles, as the person chooses

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-05, deciding where the Dev Board's Spot/Futures combo goes when the Dev Board is deleted (EPIC-033P): "Market mode thêm Spot/Futures" (the Market mode gains Spot/Futures)
**Risk:** 🟢 — the Watchlist and charts read one more choice; a mixed-market tick feed is the trap
**Complexity:** S — one choice, read where `MARKET` is read today
**Epic (optional):** [EPIC-033](../README.md)
**SPEC (optional):** [SPEC-002](../../../../Docs/SPEC/README.md)
**Depends on:** EPIC-033H (merged)

---

## 1. Context and problem
The Market mode watches Spot only: `src/modules/trading/ui/market/market_dependencies.py` fixes `MARKET = MarketType.SPOT`. The only place a person sees Futures candles outside the Futures desk is the Dev Board's Spot/Futures combo box, which EPIC-033P deletes.

## 2. Acceptance criteria
- [ ] Market → Spot and Market → Futures are two checkable actions in one exclusive group; Spot is the default and the choice persists per mode.
- [ ] The Watchlist and every open chart show the chosen market's candles; a tick from the other market never reaches them.
- [ ] Switching the market reloads the open charts and the Watchlist; nothing from the previous market stays on screen.

## 3. Design
The market is a value of the mode, not of each chart: one exclusive `QActionGroup` (HLD §11.2.3 "Market" menu), read by the presenter where it reads `MARKET` today.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/market/market_commands.py` | the two checkable actions |
| `src/modules/trading/ui/market/market_presenter.py` | the market as state; reload on change; filter ticks by market |

## 5. Testing
Unit: the actions are exclusive and persist; a tick of the other market is dropped (mutation-verified). Integration: switching reloads the charts against the in-memory store.
