# Nhiệm vụ: Intra-bar Bar Magnifier & Giải quyết Xung đột SL/TP trên cùng 1 nến

**Mã Task:** `BOT-105B`  
**Thuộc Epic:** [`BOT-105`](BOT-105_advanced_order_execution_and_risk_epic.md)  
**Độ phức tạp:** 🔴 **L (Thinking Agent)**  
**Trạng thái:** ✅ **Done (2026-09-24)**  
**Dependencies:** [`BOT-041`](../completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md), [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md)

---

## 1. Vấn đề: Nghịch lý Râu nến (Intra-bar Ambiguity)

Trong kiểm thử tĩnh (Static Backtest theo nến 5m/1h/1d):
Khi một cây nến có biên độ dao động lớn (`High` vượt qua mức `Take Profit` và `Low` đâm thủng mức `Stop Loss`):
- Nếu giả định nến chạm **TP trước** $\rightarrow$ Ghi nhận LÃI LỚN.
- Nếu giả định nến chạm **SL trước** $\rightarrow$ Ghi nhận LỖ.
- Các backtester thông thường thường chọn ngây thơ hoặc luôn lạc quan (giả định chạm TP trước) $\rightarrow$ Dẫn tới **ảo tưởng lợi nhuận (Backtest Over-optimism Bias)**.

---

## 2. Giải pháp (Bar Magnifier Engine)

Tận dụng hạ tầng Dữ liệu Tick 1s đã xây dựng từ [`BOT-076`](../completed/BOT-076_realtime_backtest_engine.md):
1. **Chế độ Static thông thường (Không có dữ liệu tick)**:
   - Áp dụng nguyên tắc phòng thủ thận trọng (Pessimistic Rule): Nếu nến chạm cả SL và TP $\rightarrow$ Luôn ưu tiên xử lý **Cắt lỗ (SL) trước**.
2. **Chế độ Nâng cao (Bar Magnifier / Phóng to thanh nến)**:
   - Khi phát hiện nến khung lớn (VD: 15m) chạm cả SL và TP, Engine tự động trích xuất chuỗi nến con 1s / 1m bên trong thanh nến đó để tái hiện quỹ đạo giá thực tế.
   - Xác định chính xác theo thời gian thực (Timestamp) xem giá chạm mốc nào trước trong lịch sử.

---

## 3. Tiêu chí Nghiệm thu

- Có test kiểm thử chứng minh: Ca nến quét 2 đầu ở chế độ thường luôn bảo thủ (cắt lỗ trước); ở chế độ Bar Magnifier xác định chuẩn xác theo chuỗi tick 1s.
- 0 lỗi tài chính, không rò rỉ dữ liệu tương lai (No Look-ahead bias).

---

## 4. Implementation Notes (2026-09-24)

**Re-verified before implementing** (this repo's own "stale backlog task"
pattern): item §2.1 (pessimistic SL-first for a plain Static bar with no
magnifier) was already fully implemented and mutation-tested by `BOT-041`
(`order_matching_policy.py`'s `if/elif` order, locked by
`test_evaluate_intrabar_stops_tie_breaker_stop_loss_wins`) — nothing to build
there. `BUG-133`'s fix (tick backtest never checked intrabar stops) also does
**not** implement §2.2's real first-touch resolution: it only re-runs the
same pessimistic tie-break at `tick_resolution` granularity (typically 1s),
narrowing the ambiguity window rather than reading a real chronological
touch order. The actual unbuilt work was §2.2's Bar Magnifier: an ambiguous
Static bar looking up real finer sub-candles to resolve the tie.

**Design.** `OrderMatchingPolicy.evaluate_intrabar_stops()` gained an
optional `magnifier_lookup: Callable[[], Sequence[tuple[float, float]]] |
None` parameter — a zero-argument, bar-scoped closure the domain calls
**lazily**, at most once per bar, only when a position is actually found
ambiguous (both SL and TP hit). This keeps the domain layer free of any
repository dependency (`architecture-rule.md` §1 Dependency Inversion — the
domain receives the narrowest possible abstraction, not
`IMarketDataRepository`) while making the extra query proportional to real
conflicts: a normal bar, and a run that never opts in, pays nothing extra.
`RunStaticBacktestCommand`/`BacktestRunConfig` gained a new
`magnifier_resolution: TimeFrame | None = None` field (default preserves
prior behavior exactly) mirroring `tick_resolution`'s own established shape;
`run_static_backtest/handler.py` builds the lookup closure per bar, calling
`IMarketDataRepository.get_klines()` for `[candle.open_time,
candle.close_time)` at the finer resolution — reusing exactly the query
`BOT-076`'s own tick engine already uses for its own finer klines, confirmed
by investigation to be the same repository/table, not separate
infrastructure. Missing/never-synced finer data (`get_klines()` returns
empty) falls back to the pessimistic default rather than raising, per this
task's own §2.1 fallback.

**Ordering correctness.** The lookup is threaded through
`PaperExchange.check_intrabar_stops()` **after** `_apply_break_even_stops()`
runs, so an ambiguous-bar decision is always made against the position's
real, current-bar stop price — never a stale pre-break-even one. Verified by
mutation: moving the break-even call to after the intrabar-stops check made
`test_check_intrabar_stops_evaluates_magnifier_against_the_post_break_even_stop`
fail for the right reason, then restored.

**Re-scope:** no UI picker for `magnifier_resolution` was added, matching
`tick_resolution`'s own precedent (`backtest_fsm_matrix.py`'s own comment:
"no resolution picker exists yet, that is optional follow-up, not required
for this mode to work correctly") — the config field is the seam
(`architecture-rule.md` §7.2.1), a UI control is the variant, deferred until
a real need shows up.

**Tests** (all mutation-verified — see file-level comments for the specific
mutations each catches): `test_order_matching_policy.py` (+8 — no-lookup
regression unchanged, TP-first and SL-first chronological resolution for
LONG and SHORT, empty-lookup fallback, still-ambiguous-at-finest-resolution
fallback, lazy no-call-when-not-ambiguous, memoization across multiple
ambiguous positions in one bar); `test_paper_exchange.py` (+2 — end-to-end
through `check_intrabar_stops()`, and the break-even-ordering test above);
`test_run_static_backtest.py` (+3 — real `IMarketDataRepository.get_klines()`
call args verified against the ambiguous bar's own `[open_time, close_time)`
window, empty-repository fallback, and `magnifier_resolution=None` never
querying the repository at all).

**Verification**: `ruff check`/`ruff format --check` clean on every touched
file. mypy (gate's real invocation — cwd at the parent directory, `MYPYPATH`
set to a sibling `Sagittarius_Engine` checkout + that parent) — zero errors
under `Sagittarius_Elite_Warrior/`, same as before this change; the 12
existing errors are all pre-existing and confined to the separate
`Sagittarius_Engine` repository. `tests/unit/modules/backtesting` +
`tests/unit/architecture` — 1318 passed, no regressions.
