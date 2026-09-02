---
name: Domain Truthfulness Rule
description: Dữ liệu trung thực — coverage thật, exchange filter thật, snapshot bất biến, không gộp ngữ nghĩa giao dịch, UI không hứa thứ engine chưa làm được, benchmark có phương pháp.
trigger: on_file_change
patterns:
  - src/domain/**/*.py
  - src/application/**/*.py
---

# TRUTHFUL DATA, VALIDATION & SNAPSHOT SEMANTICS

Nguyên tắc xuyên suốt: **hệ thống không được nói dối về thứ nó thật sự đã làm.**
Một con số hợp lệ về mặt kiểu dữ liệu vẫn có thể là lời nói dối về nghiệp vụ —
và trong một bot giao dịch, đó là tiền thật.

---

9. **Truthful Data, Validation & Snapshot Semantics:**
   - A range-coverage check MUST verify internal gaps using the timeframe cadence and normalized UTC boundaries; min/max timestamps or total row count alone do not prove coverage.
   - Exchange trading rules (minimum notional, lot size, tick size, leverage) MUST come from cached metadata for the active symbol/market. Never treat account capital as order notional and never hard-code a universal exchange filter.
   - UI history/cache snapshots MUST be immutable (no retained mutable model references), memory-bounded, and include enough provenance to describe the result honestly: configuration, data window/watermark, strategy version/parameters, fee model, and execution mode.
   - **Business Contract Before Implementation Contract:** Tests MUST first express the observable business promise, then verify the implementation. A green suite that only proves private calls, existing data structures, or an intentionally limited engine contract is not evidence that the user-facing behaviour is correct. For every critical trading journey, write deterministic acceptance coverage for the expected inputs, orders/position transitions, fills, trade side, PnL direction, and the visible table/chart outcome.
   - **Do Not Collapse Trading Semantics:** A strategy signal, order intent, execution fill, position entry, position exit, and short entry are distinct domain facts. Model and test them separately; never let an ambiguous `BUY`/`SELL` label silently stand for more than one. In a long-only engine, `SELL` is an exit of an existing LONG, not an opened SHORT.
   - **Truthful Trading UI:** Every label, icon, marker, filter, metric, and empty state MUST describe what has actually happened and what the engine supports now. A close-long marker must use a distinct exit semantic/icon from a short-entry/sell marker. Do not present a planned or unsupported capability as available; hide/disable it or explicitly label it unavailable. Test the displayed semantics, not only the underlying payload.
- Never claim instantaneous or fixed latency without a reproducible benchmark fixture. State the workload, cache condition, and measurement method; display ETA as an estimate only.
- **Renderer benchmark methodology:** A renderer comparison must drive the same immutable source payload, viewport/input sequence, event drain and completed visual grab through both implementations. Record median/p95, DPR, actual backend, environment, visual semantics and warning capture. Treat CPU/GPU frame time and business/pixel correctness as separate proofs; never improve a benchmark by dropping markers, labels, data or a final render check.
- **Backtest chart host boundary:** Use a narrow Backtest-scoped `Protocol` (`IBacktestChartHost`) and transient factory so Presenters/Backtest Views depend only on the port, never a concrete renderer directly. A host is UI-thread/view-owned and may not be singleton or hot-swapped. (A former native C++/QML host lived behind this same port and was deleted outright — the port stayed worth keeping even with one implementation.)
- **Counterintuitive Story Check:** When a story, label, default, or acceptance criterion can reasonably conflict with a user's mental model (especially a TradingView-style workflow), stop and report the observable behavior, evidence, and trade-off before finalizing the design. Do not invent a hidden user intent; encode the chosen semantics truthfully in UI copy and deterministic acceptance tests.
