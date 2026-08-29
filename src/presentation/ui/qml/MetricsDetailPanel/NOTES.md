# MetricsDetailPanel

QML redesign of "CHỈ SỐ CHI TIẾT BACKTEST" (`ExtendedMetricsDialog`/
`StatGrid` today). User decisions 2026-08-30:

1. **Build a new, standalone widget — do not touch `StatGrid`/
   `ExtendedMetricsDialog` in place.** Every other widget built this
   session got this default because nothing else existed for it yet; this
   one is different — `StatGrid`'s own `NOTES.md` says it has exactly one
   consumer, and that consumer is already wired into the live Backtest
   screen. Editing it in place would mean shipping this widget's invented
   verdict thresholds (see below) straight into a dialog a user can already
   open today.
2. **Use common financial heuristics for the verdict badges the mockup
   adds, clearly labelled as invented.** Not a specification anywhere in
   this codebase — see below for exactly which numbers are real and which
   are this widget's own guess.

## What's real, reused unchanged

`build_extended_stat_cards()` (`backtest/logic/performance_metrics_view.py`)
is not touched — `MetricsDetailVM` takes its `StatCardData` output as input
(`get_cards` callback) and does not re-derive a single value, a colour, or
a formatting rule already computed there. Same for the gross-profit-vs-loss
bar: `grossProfit`/`grossLoss`/`profitFactor` are real `BacktestMetrics`
fields, supplied via callback — the bar's proportions and the "Mỗi 1 USD
lãi đi kèm X USD lỗ" caption are arithmetic on those real numbers
(`gross_loss / gross_profit`), not new data.

`Max Drawdown Duration`'s "≈ N ngày" badge is exact unit conversion
(`bars × timeframe_seconds / 86400`), not a heuristic — it needs the run's
timeframe via `get_timeframe_seconds`, which `BacktestMetrics` itself does
not carry (duration is stored in bars, not wall-clock time).

## What's invented — needs review before this reaches a real screen

Nothing in this codebase defines "a Sharpe Ratio of X is good/bad" — these
thresholds do not exist anywhere else, domain or presentation. What is
built here, in `metrics_detail_vm.py`:

- **Sharpe/Sortino Ratio**: `<0` → "Rất kém", `0–1` → "Trung bình",
  `1–2` → "Tốt", `>2` → "Xuất sắc". A common textbook Sharpe-ratio
  convention, not something derived from this app's own data or an
  existing rule.
- **Calmar Ratio**: `<0` → "Âm", `0–0.5` → "Yếu", `0.5–1` → "Khá",
  `>1` → "Mạnh". Same caveat.
- **Max Consecutive Losses**: `≥ 10` → "Cảnh báo". The threshold `10` is
  arbitrary — picked because the mockup's example (46 losses) clearly
  crosses whatever a reasonable line is, not because `10` is a value this
  app has settled on anywhere.

Before wiring this into Backtest for real, these four heuristics should be
reviewed against how this app actually wants to characterise strategy
risk — they render correctly today, but "correctly" only means "matches
the arithmetic and colour direction the mockup implies for its one
example," not "validated against this app's own risk model."

## Grouping — mechanical, not invented

The mockup's 4 sections (LÃI & LỖ / TRUNG BÌNH MỖI LỆNH / RỦI RO / CHUỖI
LIÊN TIẾP) are a fixed title → group lookup in `metrics_detail_vm.py`, read
straight off the mockup's own layout — no judgment involved. Three cards
`build_extended_stat_cards()` returns that the mockup doesn't show (Total
Fees Paid, In-Sample/Out-of-Sample Net Profit) fall into a catch-all "KHÁC"
group instead of silently disappearing.

## Self-contained via `kit/DialogShell`, not `QmlOverlay`

Unlike `StatGrid.qml` (a `QmlOverlay` body, chrome supplied by `Overlay`),
this widget has no host screen to borrow chrome from yet, so it wraps
itself in the shared `kit/DialogShell` — its own header (accent mark,
title, close ×) and its own footer ("Copy tất cả" ghost + "Đóng" primary,
both `kit/Button`). `copyRequested`/`closeRequested` are signals with no
listener yet, same "structural pass" boundary every other widget built
this session uses.

## Not yet wired into a screen

`preview.py` constructs `StatCardData` instances directly, matching the
values in the mockup image, rather than building a full
`BacktestResult`/`BacktestMetrics` just to reach the same 14 numbers —
plus the gross-profit/loss figures from that same mockup.
