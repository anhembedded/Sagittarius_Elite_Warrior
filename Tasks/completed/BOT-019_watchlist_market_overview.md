# Nhiệm vụ: Watchlist / Market Overview

**Status**: ✅ **Done (2026-09-23)** — see §5 for what actually shipped and what is deliberately deferred.

## 1. Mục tiêu (Objective)
Cho phép theo dõi nhiều symbol cùng lúc dưới dạng bảng (giá hiện tại, % thay đổi, volume) thay vì phải mở từng ChartCard riêng lẻ — tận dụng hạ tầng Live Stream đã hoàn thiện ở BOT-005.

## 2. Mô tả (Description)
Thêm `WatchlistCard`/`WatchlistScreen` hiển thị bảng (QTableView) các symbol đang theo dõi, cập nhật realtime qua `MarketTickEvent` giống cách `ChartCard` đang nhận dữ liệu, nhưng không cần vẽ candlestick — chỉ cần giá đóng cửa gần nhất, % thay đổi so với phiên/nến trước, và volume.

## 3. Các bước thực hiện (Action Items)
- [x] `WatchlistTableModel` (QAbstractTableModel): cột Symbol / Last Price / % Change / Volume, cập nhật cell qua `dataChanged` khi có tick mới — tránh render lại toàn bảng mỗi tick.
- [x] `WatchlistPresenter` — re-scoped: constructs its own `MarketTickFeed` rather than calling `event_bus.on(MarketTickEvent, ...)` directly (see §5), map sang dòng tương ứng trong model theo symbol.
- [x] Highlight màu xanh/đỏ khi giá tăng/giảm (dùng `theme.py`'s `BULL_COLOR`/`BEAR_COLOR`) — re-scoped: persistent per-row colour by direction, not a temporary flash-on-update animation (see §5).
- [x] Danh sách symbol theo dõi lấy từ `DEFAULT_SYMBOLS` trong config qua `app_defaults.py`'s `default_symbol_options()`, với floor riêng của màn này (không phải constant `DEFAULT_SYMBOLS` trần).
- [ ] Click vào 1 dòng trong watchlist để chuyển ChartCard tương ứng lên focus — **deferred** (see §5); doc's own wording already marked this "không bắt buộc".
- [x] Unit test cho `WatchlistTableModel`/`WatchlistPresenter` theo `.claude/rules/testing-rule.md`, bao gồm 1 wiring test mutation-verified.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Nhiều symbol tick liên tục — đảm bảo update UI qua đúng cơ chế thread-safe hiện có (giống cách `dashboard_presenter.py` marshal sang main thread), không update trực tiếp từ WebSocket thread.
- Không tự ý stream thêm symbol ngoài danh sách đã cấu hình — tránh vượt rate-limit của Binance WebSocket.

---

## 5. Implementation notes (what actually shipped)

**Screen**: `src/modules/market_data/ui/watchlist/` (`watchlist_screen.py`,
`watchlist_view.py`, `watchlist_presenter.py`, `watchlist_table_model.py`,
`preview.py`) — a second screen this module contributes alongside
`database_screen()`, registered from `MarketDataModule.contribute()`. Chosen
over `trading`/a new module because `market_data` already owns
`MarketTickEvent` and its live-stream port (`IMarketStream`).

**A real architectural fix fell out of this task.** `MarketTickFeed` — the
one-subscriber-many-displayers Feed for `MarketTickEvent`
(`architecture-rule.md` §6) — lived in `modules/trading/ui/`, even though
`MarketTickEvent` is `market_data`'s own contract. A third consumer
(Watchlist) needing it from a different module would have meant either a
backward `market_data → trading/ui` import (wrong direction: `market_data`
owns the event) or a forward one (`trading → market_data/ui`, needing an
allowlist entry). Root-caused rather than patched: moved
`market_tick_feed.py` to `market_data/ui/` (the module that owns the event
it normalizes — the exact call `EPIC-025` PR 4.4a already made for
`symbol_options_coordinator`/`sync_progress_feed`), updated `trading`'s two
pre-existing consumers (`dashboard_presenter.py`, `trading_presenter.py`) to
read it from its new address via an allowlisted cross-module import, same
shape as that precedent. `allowlist_module_boundaries.txt`'s documented
count: 8 → 10.

**Live stream**: `WatchlistPresenter` calls `IMarketStream.start("watchlist",
symbols, TimeFrame.ONE_MINUTE)` directly in its constructor and `stop()` in
`shutdown()` — no `StreamLifecycleController`-style machinery, since
`IMarketStream.start()` is a synchronous, direct port call by its own
contract (not a background-threaded operation), and one owner may hold
several symbols at once, exactly this screen's shape.

**Colour, re-scoped from "highlight temporarily" to "colour by direction,
persistently".** The task's own wording ("Highlight tạm thời khi giá
tăng/giảm") describes a flash-on-update animation. Not built, for the same
reason `PROP-002`'s pulse/ring highlight was not built the same day: this
codebase has no existing per-cell flash/pulse animation precedent anywhere,
and a persistent `ForegroundRole` colour on `% Change` (bull/bear, by sign)
already tells the user the same fact — the direction — durably rather than
for a moment. Simpler, reuses an existing pattern
(`architecture-rule.md` §7.2.1 "reuse proven patterns"), no new machinery.

**Click-to-focus a displayed `ChartCard` is deferred, not built** — the
task's own text already marks it non-mandatory ("không bắt buộc phải mở
chart mới"). Locating "the chart card for this symbol, if currently
displayed" would need cross-screen state Watchlist has no way to reach
today (Dashboard/Trading each own their own `chart_cards`, not exposed to
another screen), which is real, separate infrastructure work, not a
one-line addition.

**Percent change** is computed from the tick's own candle
(`(close_price - open_price) / open_price * 100`) — the same open→close
direction convention `ChartCard.price_line` already uses for its own
bull/bear colouring — not a separate "vs. previous close" concept, which
would need retaining an extra previous-tick value this screen has no other
use for.

**Tests**: `test_watchlist_table_model.py` (9 cases — seeding, tick
update/replace/ignore-untracked, label formatting, win/loss colour
including the breakeven-is-bullish convention, re-seeding resets the
table); `test_watchlist_presenter.py` (8 cases — symbol seeding from
config/fallback, stream start under this screen's own owner id, tick
handling including the zero-open-price guard, a wiring test mutation-
verified by commenting out the `.connect(...)` line and confirming the
real-bus-published test failed for the right reason before restoring, and
stream release on shutdown).

**Duplication ratchet**: `WatchlistPresenter._handle_market_tick` shares a
name with `dashboard_presenter`/`trading_presenter`'s own methods of the
same name (the established name for "the slot `MarketTickFeed.marketTick`
connects to"), raising `test_presenter_duplication_only_shrinks.py`'s
cross-package total 66 → 67. Accepted as debt with no real extraction
target (the three bodies do genuinely different things) rather than
disguised by renaming — full reasoning in that guard's own docstring.

**Verification**: `ruff check`/`ruff format --check` clean.
`tests/unit/modules/market_data` + `tests/unit/modules/trading` +
`tests/unit/architecture` + `tests/unit/test_event_flow_guards.py` +
`tests/sanity`: 1889 + 32 passed. `mypy` (`src` + `scripts`, this repo's own
invocation): zero errors across 669 source files.
