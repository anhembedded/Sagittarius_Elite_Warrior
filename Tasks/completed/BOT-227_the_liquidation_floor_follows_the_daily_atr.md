# BOT-227 — The refusing liquidation floor follows the daily ATR

**Status:** ✅ Done (2026-10-22)
**Board:** The Futures stop-to-liquidation floor is now the larger of the owner's 1% of the exit and half a daily ATR, so the ATR can only raise it; the Start reads the same stored daily candles as the Plan and falls back to the 1% (saying why) when they are missing or stale. The 0.5 multiple is proposed for the owner's veto ([decision](epics/EPIC-039_futures_venue_profile/DECISION_2026-10-22_the_liquidation_floor_follows_the_daily_atr.md)).
**Source:** The owner, 2026-10-21: "1% giá stop bây giờ, làm theo ATR ngày sau" ([decision](../epics/EPIC-039_futures_venue_profile/DECISION_2026-10-21_a_stop_too_close_to_liquidation_is_refused.md), option C).
**Risk:** 🔴 — it moves a real-money refusal threshold.
**Complexity:** M — the Start passes no daily ATR today; the Plan already has the stored daily candles.
**Depends on:** None.

---

## 1. Context and problem
`FuturesGridThresholds.min_liq_gap_ratio` is a flat share of the exit's price. A quiet symbol is over-refused and a volatile one under-protected; `STOP_LOSS_NEAR_LIQUIDATION` already measures the gap in ATRs but only warns, and only where the daily ATR is known.

## 2. Acceptance criteria
- [x] The Start reads the same daily ATR the Plan does, so both judge one input.
- [x] A decision records the rule (the larger of the flat share and a multiple of the ATR) and its multiple. The owner's approval of the number (0.5) is **pending**: it is built as one constant for the owner's veto.
- [x] Boundary tests on both sides of the new line; the flat 1% stays the floor when no ATR is known.

## 3. Design
See [the decision](../epics/EPIC-039_futures_venue_profile/DECISION_2026-10-22_the_liquidation_floor_follows_the_daily_atr.md): `max(1 % of the exit, 0.5 × daily ATR)`, `futures_liq_gap_floor.liq_gap_floor`; one reader, `DailyAtrReader`, for the Plan and the Start.

## 3a. Reuse
`GetPlannerMarketQueryHandler`'s candle read: moved into `DailyAtrReader` and used by both. `IMarketDataSources.ports_for`: used. No UI need.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `src/modules/bots/domain/grid/futures_liq_gap_floor.py` (new) | the floor, a `max` that cannot go below the owner's share |
| `src/modules/bots/domain/grid/grid_thresholds.py` | `min_liq_gap_atr` (0.5), validated 0..`min_liq_buffer_atr` |
| `src/modules/bots/domain/grid/futures_grid_checks.py`, `futures_plan_risk_inputs.py` | `_stop` uses the floor and names its basis; `daily_atr_unavailable` carries the reason |
| `src/modules/bots/application/kinds/grid/daily_atr_reader.py` (new) | the stored daily ATR with freshness and reasons, the venue's own market |
| `src/modules/bots/application/queries/get_planner_market/handler.py` | reads through the reader (takes `IMarketDataSources` and `IBotClock`) |
| `src/modules/bots/application/services/venue/futures_start_checks.py`, `composition/futures_wiring.py`, `composition/executor_bindings.py` | the Start reads the ATR, falls back and logs |
| `src/modules/bots/ui/bots_screen/preview_frames.py` | the "liquidation warning" frame's ATR 9000 → 6000, so it still sits in the advisory band (0.5–1 ATR) |

## 5. Testing
Unit: floor boundaries on both sides and the never-below-1 % sweep (mutation `max`→`min` goes red on 14); the reader (fresh, none, too few, stale, the two-day edge); the Start's fallback and log. Bots unit tier and `tests/unit/architecture` pass. Not run: a Start on a real or fake exchange with stored candles, a refusal there.

## 6. Docs touched
`Docs/MODULES/bots/06-runtime.md` ("Built: the stop-to-liquidation floor").

## Implementation notes
Plan behaviour that changes with it: the planner reads its venue's own market's candles (it read the default venue's), and offers no ATR (so no ATR range advice) from candles whose newest is over 2 days old. Mainnet venues are unaffected unless the store is stale.
