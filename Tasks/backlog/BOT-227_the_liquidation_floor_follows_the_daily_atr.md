# BOT-227 — The refusing liquidation floor follows the daily ATR

**Status:** 🔵 Backlog
**Priority:** P3
**Board:** The Futures plan refuses an exit closer to its estimated liquidation than a fixed 1% of the exit (`BUG-255`); the owner asked for that gap to follow the symbol's daily ATR once the Start can read it.
**Source:** The owner, 2026-10-21: "1% giá stop bây giờ, làm theo ATR ngày sau" ([decision](../epics/EPIC-039_futures_venue_profile/DECISION_2026-10-21_a_stop_too_close_to_liquidation_is_refused.md), option C).
**Risk:** 🔴 — it moves a real-money refusal threshold.
**Complexity:** M — the Start passes no daily ATR today; the Plan already has the stored daily candles.
**Depends on:** None.

---

## 1. Context and problem
`FuturesGridThresholds.min_liq_gap_ratio` is a flat share of the exit's price. A quiet symbol is over-refused and a volatile one under-protected; `STOP_LOSS_NEAR_LIQUIDATION` already measures the gap in ATRs but only warns, and only where the daily ATR is known.

## 2. Acceptance criteria
- [ ] The Start reads the same daily ATR the Plan does, so both judge one input.
- [ ] A decision records the rule (for example the larger of the flat share and a multiple of the ATR) and its multiple, with the owner's approval of the number.
- [ ] Boundary tests on both sides of the new line; the flat 1% stays the floor when no ATR is known.
