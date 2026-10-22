# ADR — A Futures plan whose exit sits too close to its estimated liquidation is refused

**Epic:** [EPIC-039](README.md)
**Date:** 2026-10-21
**Status:** Accepted (2026-10-21)
**Decided by:** the owner, 2026-10-21: "1% giá stop bây giờ, làm theo ATR ngày sau" (a 1% floor now, ATR-tied later)

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the code at `68e1227` |
| 🔵 Proposed | an option awaiting a decision |
| ❓ Open | needs the owner |

## 1. Context
✅ On 2026-10-21 a Futures start passed `plan risk OK LIQUIDATION_ESTIMATE` with the exit 1.51 before the estimated liquidation (0.23% of the exit at 658) (`BUG-255`). The only near-liquidation check, `STOP_LOSS_NEAR_LIQUIDATION`, is a WARNING that needs a daily ATR the Start does not pass, and a WARNING never refuses a start (`FuturesStartChecks.refusal`). A stop that close can be skipped by a gap, leaving the liquidation.

## 2. Options
| # | Option | Trade-off |
| :-- | :--- | :--- |
| A | Refuse an exit closer than **0.5%** of its price (the first default, `FuturesGridThresholds.min_liq_gap_ratio`) | Refuses the incident (0.23%); the one existing test fixture sits at 0.58% and passes. 0.5% of 658 is 3.29 USDT of BNB, which a fast minute can cross. |
| B | **1%**, chosen by the owner (what the code does now, `FuturesGridThresholds.min_liq_gap_ratio`) | A larger floor protects more and refuses more plans that start today; at 7x a normal gap to liquidation is several per cent. |
| C | Tie the floor to the daily ATR | Needs the Start to read the stored daily candles (not wired); the Plan already has them. Adapts to the symbol's volatility. |
| D | Keep a WARNING only | The incident repeats: a warning at Start is not shown to anyone. |

## 3. Recommendation
B (1%), the owner's choice: an ATR-free check that refuses the incident, the same in the Plan and at Start. Move to C when the Start reads the daily ATR (`BOT-227`).

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | ~~Which floor?~~ Answered: 1% now (B), ATR-tied later (C) | — | 2026-10-21 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| B, 1% | `BUG-255` | Done | `tests/unit/modules/bots/domain/grid/test_a_stop_too_close_to_liquidation_is_refused.py` |
| C, ATR-tied, 1% kept as the minimum | `BOT-227` | Done | [the decision](DECISION_2026-10-22_the_liquidation_floor_follows_the_daily_atr.md) |
