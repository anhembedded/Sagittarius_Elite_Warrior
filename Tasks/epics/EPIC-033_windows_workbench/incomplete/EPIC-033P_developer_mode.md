# EPIC-033P — Developer mode: the testbed, only when developer mode is on

**Status:** 🟡 In progress (stage 1)
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
- [ ] The mode exists only while developer mode is on (Tools → Options): its screen, its commands and its probes are all gated on `dev.mode`, where today only the probes are. HLD §11.2.1's Developer row lays it out: the event log central, the probes docked right. (This line said "a chart central" until 2026-10-05; the approved HLD row says the event log, and the Market mode already owns the chart.)
- [ ] No trading command lives only here.
- [ ] The Dev Board's market half is gone: its chart column, its Indicators panel and its "Data & stream" controls (Load history, Start live, Stop live), which the Market mode replaced (`EPIC-033H`). The Developer mode's own chart, if it keeps one, is a `MarketChart`-style tab, not the Dev Board's card stack.
- [ ] The mode passes the conformance suite with no baseline row.

## 3. Design
Per EPIC-033O's approved wireframe (HLD §11.2.1, Developer row). It replaces the rest of Dev Board.

What the survey of 2026-10-05 found:
- `trading/ui/dashboard/` is 33 files, 5 761 lines; 252 unit tests in 16 files, 53 integration tests in 13 files; four god-file, mypy-exclude, ruff-debt, stock-controls and conformance baselines name its files.
- Outside the package, only `trading/module.py` (the screen, the route and six commands) and the desks (`StrategyCard`, `StrategyCardBinding`) import it; the card imported the Dev Board's view model at runtime.
- The Dev Board screen and its commands are not gated today; only contributions to the `dev_board` surface are (`src/shell/surfaces.py`, `ContributionRegistry`). Screens and commands have no `dev.mode` check (`contribute_screen`, `contribute_command`, `ScreenRegistry.modes()`).
- The app has no event log: the Dev Board's "System monitor" is its own log lines. The Engine offers `IBusObserver` (`add_bus_observer`: the event's name and handler count, on the emitting thread) and `TraceRecorder` (a ring buffer).
- One probe exists: `TradingSessionProbe` (`trading/ui/session_probe.py`).
- The Spot/Futures combo and scroll-back "load more" exist only in the Dev Board until `EPIC-033Q` and `EPIC-033S` land in the Market mode.

### Stages, one pull request each
| Stage | What | Waits on |
| :--- | :--- | :--- |
| 1 | The strategy card moves to `trading/ui/desk/strategy_card/` and becomes stock controls (a `QGroupBox` over a `QFormLayout`); the Dev Board binds it through `dev_board_strategy_card()`. Nothing outside the Dev Board imports `trading/ui/dashboard/` but `module.py`. **The desk package is a temporary home**: HLD §11.2.4 maps the desks' strategy cards to a row per venue in Bots, §11.2.5 to the Strategy panel in `strategy/ui/panels/`, and `EPIC-033K` stage 3 deletes the card; this stage only unblocks the Dev Board's deletion, and the Bots session's stage 3 removes `desk/strategy_card/` with the card | — |
| 2 | The Developer mode: a screen of its own whose central widget is the event log (an `IBusObserver` feeding a bounded list model, marshalled to the UI thread), its probes docked right from the surface that today is `dev_board`; screens and commands gain the `dev.mode` gate descriptors already have, so the mode exists only under developer mode. The Dev Board stays beside it | stage 1 |
| 3 | The Dev Board is deleted: the package, its route and six commands, its tests (the F9 tests re-homed on the desks, the `BUG-134` regression on the card), its baseline rows lowered, SPEC-001, 002, 004, 005, 011 and 012 and the HLD reworded, `diagrams/hld-05b_trading_devboard_slots.puml` included (it still draws the card as a kit `Panel`) | stage 2, `EPIC-033Q` and `EPIC-033S` merged |

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/trading/ui/dashboard/` | Deleted once Market, Trade and this mode cover it |

## 5. Testing
Integration: conformance suite; dev-mode gating.

## Implementation notes (written when done)
- **Stage 1 (2026-10-05).** `StrategyCard` and `StrategyCardBinding` live in `trading/ui/desk/strategy_card/`. The card is a stock `QGroupBox` titled "Strategy" over a `QFormLayout` with access keys; the kit `Panel`, eight styling calls (three `StyledButton`s, five style sheets), four fixed heights and the green/grey colour on the armed line are gone (the line's words already say whether a strategy is armed). The parameters dialog is imported at the top of the module, so the `BUG-134` regression patches it there. The Dev Board builds its copy through `dev_board_widgets/dev_board_strategy_card.py`. Ratchets lowered: stock controls (`strategy_card.py` −8 style sheet, −4 fixed size), app styling (style-sheet calls 51 → 46, files 14 → 13, palette files 19 → 18), ruff `PLC0415` (−1), god file `dev_board_panel.py` 548 → 547.
