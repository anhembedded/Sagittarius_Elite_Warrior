# EPIC-033P — Developer mode: the testbed, only when developer mode is on

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "Đừng bị UI hiện tại dẫn dắt nhé, bạn có quyền xây lại triết lý và desihn của tất cả UI" (do not be led by the current UI; you may rebuild the philosophy and design of the whole UI); the modes come from EPIC-033O's approved information architecture, not from the screens that exist today.
**Risk:** 🟢 — developer-only
**Complexity:** S
**Epic:** [EPIC-033](../README.md)
**SPEC:** [SPEC-011](../../../../Docs/SPEC/SPEC-011_start_the_app_and_choose_developer_mode.md)
**Depends on:** EPIC-033O, EPIC-033C, EPIC-033D, EPIC-033F, EPIC-033G

---

## 1. Context and problem
Dev Board mixes developer probes with trading controls and market watching; the approved design splits those into Market and Trade, leaving a developer testbed.

## Decisions (the user, 2026-10-05)
What only the Dev Board offers today, and where each goes when it is deleted:
- **Last signal** (the armed strategy's last signal; only the Dev Board shows it): dropped, shown nowhere.
- **Futures candles outside the Futures desk** (the Dev Board's Spot/Futures combo): the Market mode gains a Spot/Futures choice for its Watchlist and charts, in a small pull request of its own.
- **F9 New order…** (only the Dev Board has it): each desk gets Trade → New order… (F9), which moves the focus to its order entry, as HLD §11.2.3's table lists it.
- **Scroll-back "load more" and a date range on Load history**: a task of its own for the Market mode's charts; the Developer mode does not keep them.

The Dev Board runs no strategy loop of its own: signals become orders in the `strategy` module, built at boot, whether or not the board exists.

## 2. Acceptance criteria
- [ ] The mode exists only while developer mode is on (Tools → Options); it holds a chart central and the developer probes and script console as docks.
- [ ] No trading command lives only here.
- [ ] The Dev Board's market half is gone: its chart column, its Indicators panel and its "Data & stream" controls (Load history, Start live, Stop live), which the Market mode replaced (`EPIC-033H`). The Developer mode's own chart, if it keeps one, is a `MarketChart`-style tab, not the Dev Board's card stack.
- [ ] The mode passes the conformance suite with no baseline row.

## 3. Design
Per EPIC-033O's approved wireframe. It replaces the rest of Dev Board.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/dashboard/` | Deleted once Market, Trade and this mode cover it |

## 5. Testing
Integration: conformance suite; dev-mode gating.

## Implementation notes (written when done)
Not started.
