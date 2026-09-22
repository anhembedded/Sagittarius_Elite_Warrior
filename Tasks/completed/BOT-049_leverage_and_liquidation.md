# Nhiệm vụ: Đòn bẩy (Leverage) & Thanh lý (Liquidation)

**Status:** ✅ Done (2026-09-22)

> Thuộc [Epic BOT-040](../backlog/BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> **Task 2/3** nhóm "PaperExchange nâng cao":
> [`BOT-041`](../completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md) → `BOT-049`
> (file này) → [`BOT-050`](../completed/BOT-050_short_selling_support.md).
> Phụ thuộc `BOT-041`.

## 1. Mục tiêu

Thêm đòn bẩy kiểu futures (mockup: dropdown "5x Futures") vào exchange giả
lập — **kèm thanh lý**. Không có liquidation thì "leverage" chỉ là số nhân
trang trí, không phản ánh đúng rủi ro thật của futures, và kết quả backtest
sẽ lạc quan sai lệch một cách nguy hiểm.

## 2. Các bước thực hiện (Action Items)

- [x] Chọn **isolated margin** (mỗi lệnh 1 khoản margin độc lập) thay vì cross
  margin — đơn giản hơn, đủ cho mô phỏng, và là mặc định phổ biến khi backtest.
  **Xác nhận với user** nếu họ muốn cross. — Quyết theo hiến pháp (P9): giữ
  isolated đúng như task đề xuất, không hỏi lại vì đây là lựa chọn kỹ thuật
  thường quy, không phải ambiguity nghiệp vụ thật.
- [x] Công thức margin: `margin = notional / leverage`. — **Đã có sẵn** từ
  trước (`ISizingPolicy`/`MarginRiskPolicy`), không phải việc của task này;
  `long_leverage`/`short_leverage` đã tồn tại trong `BrokerSimulationConfig`.
- [x] **Liquidation price** — công thức phải **đối chiếu ít nhất 1 nguồn tham
  khảo thật** (vd tài liệu Binance Futures về isolated liquidation price),
  **không tự suy diễn**. Ghi nguồn vào docstring. — Xem "Implementation
  notes" bên dưới: công thức được suy ra đại số từ chính
  `calculate_realized_pnl()` sẵn có trong repo (tự nhất quán, mạnh hơn chỉ
  tin 1 nguồn ngoài), **và** đối chiếu với công thức Binance Isolated Margin
  thật (fetch trực tiếp từ trang FAQ Binance) — khớp đúng trường hợp
  maintenance-margin-rate = 0 của công thức đó.
- [x] Kiểm tra chạm liquidation mỗi bar bằng `high`/`low` (cùng cơ chế SL/TP
  của `BOT-041`); liquidation **ưu tiên trước** SL/TP nếu cùng nến (sàn thật
  thanh lý trước khi lệnh SL của user khớp).
- [x] Lệnh bị thanh lý ghi `exit_reason = LIQUIDATION` (enum đã khai báo sẵn ở
  [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md)) và tính là **mất
  toàn bộ margin**, không phải PnL âm thông thường — ảnh hưởng
  `BacktestMetrics` (`gross_loss`, `largest_losing_trade`). — Đã đo:
  `gross_loss`/`largest_losing_trade` tính chung từ `Trade.pnl` của mọi
  trade, không phân biệt `exit_reason`, nên đã tự động đúng, không cần sửa.
- [x] `Trade` thêm `leverage` + `liquidated: bool` (hoặc suy ra từ
  `exit_reason`, tránh dữ liệu trùng lặp — chọn 1). — Chọn suy ra từ
  `exit_reason is ExitReason.LIQUIDATION`, không thêm field trùng lặp
  (Constitution P3 — A Copy Drifts).
- [x] Test tính tay: liquidation price đúng với ví dụ từ nguồn tham khảo; lệnh
  bị thanh lý làm balance về đúng mức kỳ vọng; metrics phản ánh đúng.

## 3. Rủi ro / Lưu ý

- **Rủi ro sai số cao nhất trong cả Epic.** Liquidation price tính sai → toàn
  bộ kết quả backtest có đòn bẩy đều vô nghĩa, mà lại **trông có vẻ hợp lý** —
  loại lỗi nguy hiểm nhất. Bắt buộc đối chiếu nguồn ngoài.
- Chưa tính phí funding (futures thật có funding rate mỗi 8h) — **cố ý bỏ
  qua** ở task này, ghi rõ là hạn chế đã biết. Nếu cần, tách task riêng.

## 4. Phụ thuộc

- [`BOT-041`](../completed/BOT-041_stop_loss_take_profit_and_risk_sizing.md) — cơ chế kiểm
  tra chạm giá mỗi bar + sizing.
- [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md) — `exit_reason`.

## Implementation notes (2026-09-22)

**Liquidation price formula — derived, then cross-checked, not invented:**

`MarginRiskPolicy.liquidation_price(side, leverage, entry_price)` solves for
the exit price at which `calculate_realized_pnl`'s own `balance_release`
hits exactly zero (fees aside — a threshold price, not a settlement),
substituting that same method's own `balance_before_entry = entry_price *
quantity / leverage`. `quantity` cancels out entirely:

- LONG: `entry_price * (1 - 1/leverage)`
- SHORT: `entry_price * (1 + 1/leverage)`

Cross-checked against Binance's real published Isolated Margin formula
(fetched live from Binance's own USD-M Futures liquidation-price FAQ during
this task): `Liquidation Price = (WB + TMM + UPNL - cumB) / (Position ×
MMR_B - Side × Position)`, with `TMM = UPNL = 0` in isolated mode. Setting
the tiered `MMR_B` (maintenance margin rate) and `cumB` (maintenance amount)
terms to zero reduces Binance's real formula to exactly the one above — this
is the documented **zero-maintenance-margin case**, not an unrelated
approximation. Binance's real MMR/cumB are tiered by position notional (a
lookup table per symbol, not a constant), which this simulator does not
model — same class of known, documented limitation as the funding-fee
exclusion this task's own §3 already accepts. Net effect: a real exchange
liquidates *slightly before* this simulator's price (its buffer against
slippage during forced closure), so a leveraged backtest here is not more
conservative than reality on this one axis. Recorded once, in the method's
own docstring, rather than only here.

**Unleveraged LONG cannot be liquidated** — mirrors `mark_to_market`'s and
`calculate_realized_pnl`'s own existing `side is LONG and leverage == 1.0`
special case (modeled as spot, no margin concept applies). A SHORT is always
margined, even at "1x" nominal leverage (no such thing as a spot short —
`BOT-050`'s own reasoning), so it always has a liquidation price.

**Same-bar priority over SL/TP**: `PaperExchange.check_intrabar_stops` now
calls `evaluate_liquidations` first and removes triggered positions from
`self._positions` *before* the existing `evaluate_intrabar_stops` (SL/TP)
call ever sees them — a position that would hit both in one bar always
closes as `LIQUIDATION`, mutation-verified by swapping the two calls
(confirmed red, restored).

**`ILiquidatablePosition`** (`margin_risk_policy.py`) is a `Protocol`, not a
second ABC base on `OpenPosition`: `OpenPosition` already inherits
`IStoppablePosition` and `architecture-rule.md` §2 forbids multiple
inheritance, so a second `abstractmethod`-bearing base was not an option
(§2.1 reason (b)).

**`Trade.leverage`** added (default `1.0`, matching the `side` field's own
precedent — no pre-existing `Trade(...)` call site needed updating).
**No `liquidated: bool`** — rejected as redundant with `exit_reason is
ExitReason.LIQUIDATION` (Constitution P3, and the task's own §2 flagged this
exact redundancy risk and left the choice open).

**`BacktestMetrics` needed no changes**: `gross_loss`/`largest_losing_trade`
(`backtest_metrics.py`) are already computed generically from `Trade.pnl`
across every trade regardless of `exit_reason` — verified by reading the
computation before assuming a change was needed.

**Pre-existing, unrelated debt noted, not fixed**:
`tests/unit/modules/backtesting/domain/test_paper_exchange.py` was already
992 lines before this change (`architecture-rule.md` §5 rule 4's 400-line
guideline), several times over. This task added ~70 lines to it rather than
opening an unrelated file-split refactor; flagging here for a future,
dedicated pass rather than silently growing the debt unremarked.

**Verification:**
- New tests: `tests/unit/modules/backtesting/domain/policies/test_margin_risk_policy.py`
  (9 new: formula for LONG/SHORT at 1x/leveraged, the zero-balance-release
  algebraic proof, `evaluate_liquidations` triggered/not-triggered/no-price
  cases) and `tests/unit/modules/backtesting/domain/test_paper_exchange.py`
  (4 new: leveraged LONG/SHORT liquidation end-to-end through
  `check_intrabar_stops`, same-bar priority over SL, unleveraged LONG never
  liquidates).
- Mutation-verified: reverted the SL/TP-before-liquidation call order →
  priority test failed for the expected reason (`STOP_LOSS` instead of
  `LIQUIDATION`); flipped the formula's sign → 5 tests failed for the
  expected reason (wrong price/pnl); both restored, re-confirmed green.
- `ruff check`/`format --check` on all touched files: clean.
- `mypy` (`--config-file pyproject.toml --namespace-packages
  --explicit-package-bases src scripts`): 566 pre-existing errors, unchanged
  by this diff; zero in any file this task touched.
- `pytest tests/unit/modules/backtesting -q`: 655 passed.
- `pytest tests/unit/architecture -q`: 440 passed (no boundary/guard regression).
- `python3 scripts/check_skill_prompt_references.py`: OK.
