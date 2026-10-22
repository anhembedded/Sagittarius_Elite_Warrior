# ADR — The stop-to-liquidation floor is the larger of the owner's 1 % and half a daily ATR

**Epic:** [EPIC-039](README.md)
**Date:** 2026-10-22
**Status:** Proposed — built for the owner's veto: the rule (D1) is the owner's, the multiple (D2) is a proposal that only raises the floor and is one constant
**Decided by:** D1 the owner, 2026-10-21: "1% giá stop bây giờ, làm theo ATR ngày sau" (a 1% floor now, ATR-tied later), recorded in [the BUG-255 decision](DECISION_2026-10-21_a_stop_too_close_to_liquidation_is_refused.md) option C; D2 the author session, which is real-money and so waits for the owner's word
**Supersedes / superseded by (optional):** completes option C of the decision above; it keeps option B (1 %) as the minimum

| Label | Meaning |
| :--- | :--- |
| ✅ Established | confirmed on the code at `ab2f70f` |
| 🟢 User decision | decided by the owner; quoted, then translated |
| 🔵 Proposed | awaiting the owner's confirmation or veto |

## 1. Context
✅ `FuturesGridThresholds.min_liq_gap_ratio` (1 %) refuses an exit nearer its estimated liquidation than that share of the exit's price (`BUG-255`). It is blind to volatility: a quiet symbol keeps a gap it does not need, and a volatile one keeps a gap a normal day crosses. The Plan has the symbol's stored daily candles (`GetPlannerMarketQueryHandler`); the Start passed no ATR to `PlanRiskInputs`, so the ATR could only ever speak in the Plan, and only as a WARNING (`STOP_LOSS_NEAR_LIQUIDATION`, 1 ATR).

## 2. Decisions
| # | Decision | Status | Decided by | Consequence |
| :-- | :--- | :--- | :--- | :--- |
| D1 | The floor is `max(1 % of the exit, M × daily ATR)`; the 1 % is always the minimum, the ATR can only raise it | 🟢 Accepted | the owner, 2026-10-21 (translated above), and 2026-10-22 ("do these three in one PR") | A missing, zero or tiny ATR leaves the 1 % exactly as before; no value of `M` can lower it (a test sweeps both). |
| D2 | `M` = `FuturesGridThresholds.min_liq_gap_atr` = **0.5**, never above `min_liq_buffer_atr` (1) | 🔵 Proposed | the author session; the owner may veto or change the number (one constant) | At 0.5 the ATR raises the floor only when the daily ATR exceeds 2 % of the exit (0.5 × ATR > 1 %). The advisory WARNING at 1 ATR stays, so a gap between 0.5 and 1 ATR warns and below 0.5 refuses. |
| D3 | The Start reads the stored daily candles through the Plan's reader (`DailyAtrReader`), the venue's own market's (`BUG-172`) | ✅ Built | the author session | One estimate for the Plan and the Start. The Plan now also reads its own venue's candles, not the default venue's, and offers no ATR from candles whose newest is over 2 days old. |
| D4 | Candles missing, too few (< 15), older than 2 days or unreadable: the flat 1 % stands, the refusal's words and the log (`[plan-risk]`) say why | ✅ Built | the owner's instruction, 2026-10-22 | Never a guessed ATR; never a raise at Start. |

## 2a. Figures (illustrations, not measured ATRs)
| Exit | Daily ATR | 1 % share | 0.5 × ATR | Floor | Effect |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 658 (the `BUG-255` incident, BNB) | 20 (3.0 %) | 6.58 | 10.00 | **10.00** | +52 % over today; the incident's gap 1.51 was refused at 1 % already |
| 60,000 (BTC) | 1,800 (3.0 %) | 600.00 | 900.00 | **900.00** | +50 % |
| 60,000 | 1,200 (2.0 %) | 600.00 | 600.00 | 600.00 | equal: no change |
| 3,000 (ETH) | 45 (1.5 %) | 30.00 | 22.50 | 30.00 | no change: the 1 % holds |
| any | missing or stale | 1 % | – | 1 % | no change, reason stated |

## 3. Alternatives considered
| Option | Why it lost |
| :--- | :--- |
| `M` = 1 (the existing advisory buffer) | Turns every warning into a refusal at once; the plans that start today and would stop starting are the most. Kept as the next step if the owner wants it, one constant. |
| Replace the 1 % by the ATR rule | Violates P8: a quiet symbol or a missing ATR would loosen a refusal the owner set. |
| A separate WARNING-only ATR check at Start | The incident repeats: a warning at Start is not shown (`BUG-255`, option D). |

## 4. Open questions
| # | Question | Blocks | Asked on |
| :-- | :--- | :--- | :--- |
| O1 | Does the owner confirm `M` = 0.5, or want another number (a value between 0 and 1)? | nothing built: it is one constant | 2026-10-22 |

## 5. Implementation evidence
| Decision | Delivery task | State | Evidence |
| :--- | :--- | :--- | :--- |
| D1, D2 | `BOT-227` | Done | `tests/unit/modules/bots/domain/grid/test_the_liquidation_floor_follows_the_daily_atr.py` |
| D3, D4 | `BOT-227` | Done | `tests/unit/modules/bots/application/kinds/grid/test_the_start_reads_the_same_daily_atr_as_the_plan.py` |
