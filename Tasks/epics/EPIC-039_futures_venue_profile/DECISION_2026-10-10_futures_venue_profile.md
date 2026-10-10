# ADR — Futures is a venue profile shared by every bot kind; the open choices are the owner's

**Epic:** [EPIC-039](README.md)
**Date:** 2026-10-10
**Status:** Accepted for D1–D4 (the owner accepted the evaluation that contains them); Proposed for D5–D6; **O1–O12 are open and pending the owner**, each with a recommendation
**Decided by:** D1–D4 the owner, 2026-10-10: after the evaluation in chat (venue profile, one-way mode, Long first) the owner answered *"ok, sau đó mở epic cho cái này, chính bạn sẽ viết design, task, v.v... sau đó push. đảm bảo khi sonet đọc epic sẽ nắm hết được thông tin"* (translated: ok, then open an epic for this; you write the design, tasks etc. and push; make sure that when Sonnet reads the epic it has all the information). D5–D6 are the epic author's proposals. O1–O12: Pending.

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the real code tree; cited as `file:line` |
| 🔵 Proposed | an option awaiting a decision; not accepted |
| 🟢 User decision | decided by the user; quoted, then translated |
| ❓ Open | blocks the named phase until answered |

## 1. Context
The Grid bot is Spot-only: nine hard-coded Spot places outside `ui/`, six inside, and a Spot meaning (opening buy, base balances, inventory budget, `BaseHandling`) that is not a branch ([DESIGN §1.2](DESIGN_2026-10-10_futures_venue_profile.md)). The Futures building blocks already exist in `trading` ([§1.1](DESIGN_2026-10-10_futures_venue_profile.md)). The owner's goal is that **every bot added later has a Futures side and a Spot side**, so the fork is made once in shared ports. The owner's own halt of 2026-10-09 (a Spot ladder cancelled, the base left held) is the case Futures cannot afford ([RESEARCH §7](RESEARCH_2026-10-10_futures_grid.md)).

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | **Futures is a venue profile, shared by every kind**; a kind declares supported profiles and uses shared ports (`IVenueProfiles`, `IExposureBook`, `IRiskGuard`, `ICostModel`, `IVenueSettingsGate`, `IVenueFacts`). No `market_type is SPOT` outside the one profile adapter; a guard enforces it. | Accepted | 🟢 the owner | `EPIC-029K` is superseded (moved to `EPIC-029/cancelled/`); Phase 0 is a refactor under green Spot tests. |
| D2 | **One planner for all directions**: direction is the opening exposure of the same ladder (`position(P) = q·(k(P) − c)`); Spot is Long at leverage 1 and the regression oracle. | Accepted as the direction to try; confirmed or rejected by `039B`'s property test | 🟢 the owner (the evaluation said Spot = Long at 1×) | If the property test disproves the model for Neutral, `039B` stops and reports before building on it. |
| D3 | **One-way position mode only**; the bot never changes position mode. | Accepted | 🟢 the owner (the evaluation) | The existing `HEDGE_MODE_UNSUPPORTED` check stays the door. |
| D4 | **USDⓈ-M perpetuals only** (`MarketType.FUTURES_USD_M`). | Accepted | 🟢 the owner (the evaluation) | Coin-M, delivery, Spot margin are extension cases (DESIGN §11). |
| D5 | The shared ports live in `src/modules/bots/contracts/`; adapters call `trading/contracts` only; `trading` stays the only order sender; the position derivation is a new trading-side deriver beside `owner_inventory_deriver.py`. | 🔵 Proposed | Pending | Keeps the module boundary guard's allowlist from growing; the alternative (ports in `core/contracts/`) would make a bots concept part of the shared kernel. |
| D6 | `BaseHandling` is **renamed** `ExposureHandling` (`KEEP`, `CLOSE_AT_MARKET`) in one mechanical commit (`039B`). | 🔵 Proposed | Pending | "Base" is a Spot word; a Futures `CLOSE_AT_MARKET` is a reduce-only close. A rename touches every importer in `src/`, `scripts/` and `tests/`. |

## 3. Alternatives considered
| Alternative | Why it lost |
| :--- | :--- |
| A second kind `FuturesGridKind` | Duplicates spacing, levels and fill accounting; the next kind would fork again; `EPIC-029K` and `IBotKind`'s own docstring already rejected it. |
| Make the Spot executor generic by adding `if futures:` branches | A dozen branches would become dozens; the guard of D1 exists to forbid exactly this; each branch is a Spot-regression risk. |
| Cross margin first | The liquidation estimate is optimistic under Cross (it sees one position), so the guard would under-warn; Isolated first (O5). |
| Hedge Mode support | Account-wide, cannot change with orders open, forbids `reduceOnly` (RESEARCH §3), and `LivePosition` is one-way by design. |
| Treat the exchange's grid product as the engine (a Binance-side grid) | Not an API this app has; it would remove the executor, the reconcile and the owner's control. |
| Build Futures Neutral first (Pionex recommends its liquidation profile) | It has no Spot oracle, two liquidation estimates and no reduce-only; Long first reuses the most proven code (O1). |

## 4. Open questions (pending the owner; each with a recommendation)
**Do not decide any of these in code. Ask, with the options and the recommendation, in the task that needs it.**

| # | Question | Options | Recommendation | Blocks |
| :-- | :--- | :--- | :--- | :--- |
| O1 | Which direction first, and in what order? | Long → Short → Neutral · Neutral first · all three at once | **Long, then Short (a sign flip of Long), then Neutral.** Long is the smallest step from the Spot executor and has the Spot oracle. | 039H, 039I |
| O2 | What does `capital_quote` mean on Futures? | the margin the user commits (and `leverage` multiplies it) · the notional the bot may reach | **Margin, with a `leverage` key;** the planner keeps the worst-case notional ≤ `capital × leverage` and ≤ the bracket cap. A Spot bot is leverage 1. | 039B, 039F |
| O3 | Is a stop loss mandatory on a leveraged bot? | REFUSED without one when leverage > 1 · WARNING only · off | **REFUSED when leverage > 1 and no stop loss; WARNING at leverage 1.** A leveraged grid without a stop ends in liquidation (RESEARCH §1). The user's rule "the bot never fixes a parameter" is kept: it refuses, it does not add one. | 039F |
| O4 | Leverage default and ceiling in the UI | start at 1× · start at a low value (2×) · no ceiling beyond the bracket | **UI starts at 2×; WARNING above 10×; REFUSED above the bracket and above a configurable ceiling (default 20×).** Thresholds in `FuturesGridThresholds`. | 039F, 039J |
| O5 | Margin mode | Isolated only · Isolated and Cross | **Isolated only in this epic;** Cross needs the other positions' maintenance margin (extension case). | 039E, 039F |
| O6 | What a Futures bot does when the price leaves the range | `hold` (idle at max exposure) · `close` (close and stop) | **`hold` by default, `close` as an option,** with a `RANGE_EXIT` alert (`EPIC-036B`); both stated on the Plan. | 039H |
| O7 | When may a Futures **mainnet** venue run a bot? | as soon as built · after protective stop + owner-run soak · never | **Not before `039L`: a protective stop for every position and the owner's 14-day unattended soak on Futures testnet;** until then Futures mainnet is not offered in the bot venue picker. | 039J, 039L |
| O8 | What does a halt do with a Futures position? | leave it (as Spot leaves base) · close it reduce-only · leave it only under an exchange-side stop | **Close it reduce-only unless an exchange-side stop stands;** with one standing, leave it. A leveraged position is never left bare. | 039H, 039L |
| O9 | Backtest scope on Futures | candles only · + funding · + funding and liquidation | **Funding and liquidation included** — a backtest that ignores them flatters a leveraged grid; funding history source to verify. | 039K |
| O10 | Order flags for ladder orders | `reduceOnly` on Long/Short counters · post-only (`GTX`) | **`reduceOnly` on counters yes (safe by §5); post-only no until Binance's `GTX` semantics are confirmed (RESEARCH §4).** | 039H |
| O11 | Where does the position derivation read from? | the owner's tagged fills (like Spot, ADR D6) cross-checked with `positionRisk` · `positionRisk` alone | **Tagged fills, cross-checked** — consistent with "never supplied by the owner"; `positionRisk` alone cannot tell the bot's position from a foreign one. | 039D |
| O12 | Does a headless `run` host (EPIC-038) stop a Futures bot differently? | one policy for all · per profile | **Per profile:** "leave orders resting" is not acceptable for a Futures bot without a protective stop (DESIGN §12). Record the answer in both epics. | 039L, `EPIC-038D` |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1 | 039A, 039M | Not started | Not yet verified |
| D2 | 039B | Not started | the property test is the evidence |
| D3 | 039E | Not started | Not yet verified |
| D4 | 039A | Not started | Not yet verified |
| D5 | 039A, 039D | Not started | Not yet verified |
| D6 | 039B | Not started | Not yet verified |
