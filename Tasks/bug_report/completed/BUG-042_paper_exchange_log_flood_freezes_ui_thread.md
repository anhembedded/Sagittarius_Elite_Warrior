# BUG-042 — Backtest nhiều trade làm đơ cứng UI: `PaperExchange` log INFO mỗi lệnh khớp, đổ thẳng vào `LogListModel` trên UI thread

**Trạng thái:** ✅ Fixed 2026-08-24 (root-caused / reproduced / regression-tested / verified)  
**Phát hiện:** 2026-08-24, user báo *"trong lúc tính toán backtest là nó khóa cứng UI luôn"*  
**Mức độ:** 🔴 P1 — đơ tỉ lệ thuận số trade; backtest thật dễ vượt xa 838 trade của mẫu này  
**Log gốc:** `log-text.log` (user cung cấp, chạy 2026-08-24 19:10)  

---

## 1. Triệu chứng

Chạy Static Backtest BTCUSDT 1m, `ema_crossover`, 45.905 nến. Trong lúc backtest chạy, toàn
bộ UI đơ cứng — không bấm được gì. Backtest **vẫn chạy đúng và xong bình thường** (838 trades,
2.0 giây) — đây thuần là lỗi UI thread bị bội thực sự kiện, không phải lỗi tính toán.

Quan trọng: **không phải lúc nào cũng bị**. Số trade càng nhiều, đơ càng lâu — nên trước đây
dễ bị bỏ qua như "flaky".

## 2. Nguyên nhân thật — đã verify từng mắt xích, không đoán

### 2.1 Nguồn: `PaperExchange` log INFO mỗi lệnh khớp

3 dòng `logger.info` chạy trên **mỗi trade**:

| Dòng | File |
| :--- | :--- |
| `[paper-exchange] BUY/SELL filled \| Price: ... \| Qty: ...` | [`paper_exchange.py:326`](../../../src/domain/backtesting/paper_exchange.py) |
| `[paper-exchange] SELL filled \| ... PnL: ... \| Reason: ...` | [`paper_exchange.py:387`](../../../src/domain/backtesting/paper_exchange.py) |
| `[paper-exchange] All positions closed (N trades) \| New Balance: ...` | [`paper_exchange.py:425`](../../../src/domain/backtesting/paper_exchange.py) |

Đếm thật trên log mẫu — **5.028 dòng `App.PaperExchange`, toàn bộ nằm gọn trong 2 giây**
(19:10:19,137 → 19:10:21,141):

```
$ grep -c "App.PaperExchange" log-text.log
5028
```

### 2.2 Cầu nối: `SignalLogHandler` bắt **toàn bộ** logger gốc `"App"`

[`data_management_presenter.py:107-111`](../../../src/presentation/ui/screens/data_management/data_management_presenter.py):

```python
self._log_handler: SignalLogHandler | None = SignalLogHandler(self.ui_log_signal)
self._log_handler.setLevel(logging.INFO)
logging.getLogger("App").addHandler(self._log_handler)
```

Handler này do màn **Data Management** cài, nhưng gắn vào logger **gốc** `"App"` ở mức INFO —
nên **mọi** `App.*` của **mọi** subsystem đều chảy qua, kể cả `App.PaperExchange` của Backtest
ở màn hình hoàn toàn khác. Bất kỳ subsystem nào log per-event ở INFO đều làm nghẽn UI thread.

[`signal_log_handler.py:31`](../../../src/presentation/ui/screens/data_management/signal_log_handler.py):

```python
def emit(self, record: logging.LogRecord) -> None:
    self.signal.emit(self.format(record))   # queued cross-thread -> UI thread
```

Backtest chạy trên `IThreadManager` pool, nên mỗi `emit` là một
**queued cross-thread signal** xếp hàng sang UI thread.

### 2.3 Đích: mỗi dòng log = 1 chu kỳ cập nhật model trên UI thread

`ui_log_signal` → `_append_log` ([`data_management_presenter.py:299`](../../../src/presentation/ui/screens/data_management/data_management_presenter.py))
→ `LogListModel.append()`:

```python
def append(self, message: str, level: str = _DEFAULT_LEVEL) -> None:
    if len(self._entries) >= MAX_ENTRIES:
        self.beginRemoveRows(...); self._entries.pop(0); self.endRemoveRows()
    self.beginInsertRows(QModelIndex(), position, position)
    self._entries.append(...)
    self.endInsertRows()
    self.countChanged.emit()
```

`MAX_ENTRIES` bị chạm rất sớm, nên từ đó về sau **mỗi** dòng chạy đủ cả
`beginRemoveRows`/`endRemoveRows` **và** `beginInsertRows`/`endInsertRows` **và**
`countChanged.emit()`.

### 2.4 Kết luận chuỗi

> 838 trades × 3 dòng INFO = **~5.000 chu kỳ remove+insert+countChanged trên UI thread trong
> ~2 giây** → UI thread không còn khe nào xử lý input/paint → **đơ cứng**.

## 3. KHÔNG phải do `EPIC-006` / xoá native chart

Đã kiểm tra và loại trừ bằng code thật:
- Backtest vẫn submit vào thread pool đúng cách — không chạy trên UI thread.
- Throttle progress của [`BUG-033`](../completed/BUG-033_realtime_backtest_progress_flood_freezes_ui_thread.md)
  (`ProgressThrottle`) vẫn còn nguyên ở cả 2 handler — đường progress **không** phải thủ phạm lần này.
- Đây là lỗi per-event logging ở `INFO` vi phạm `.agents/rules/logging-rule.md` §4 và §6.

## 4. Cách sửa (Fix)

1. **Tuân thủ đúng `logging-rule.md` Rule 4 & 6:**
   - Chuyển 3 điểm log per-trade fill/close trong [`paper_exchange.py`](../../../src/domain/backtesting/paper_exchange.py)
     (`_create_position`, `_close_one_position`, `_close`) từ `logger.info` thành `logger.debug`.
   - Giữ lại dòng initialization (`[paper-exchange] Initialized for {symbol}...`) ở `INFO` (operation summary / environment).
   - Ở `--dev`/`--debug` mode, thông tin chi tiết từng trade vẫn được ghi đầy đủ vào `logs/dev-*.log` cho mục đích chẩn đoán mà không làm nghẽn UI thread.
   - `SignalLogHandler` (cấu hình ở `logging.INFO`) tự động bỏ qua các bản ghi `DEBUG`, bảo vệ UI thread 100% khỏi tình trạng nghẽn hàng đợi sự kiện.

## 5. Regression Test

- File: [`tests/unit/domain/backtesting/test_bug042_paper_exchange_log_level.py`](../../../tests/unit/domain/backtesting/test_bug042_paper_exchange_log_level.py)
  - `test_bug042_paper_exchange_per_trade_fills_do_not_emit_at_info_level`: Xác nhận khi chạy nhiều trade ở level `INFO`, chỉ có duy nhất 1 log khởi tạo, không có bất kỳ dòng log khớp/đóng lệnh nào phát ra ở `INFO`.
  - `test_bug042_paper_exchange_emits_detailed_fill_logs_at_debug_level`: Xác nhận ở level `DEBUG` (`--dev` mode), các log chi tiết lệnh mua/bán/đóng vị thế vẫn được phát ra đầy đủ.
  - `test_bug042_signal_log_handler_not_flooded_by_paper_exchange_during_backtest`: Xác nhận khi gắn `SignalLogHandler` (INFO) vào logger `"App"`, quá trình backtest 50 trade không hề gửi tín hiệu per-trade nào sang UI thread (chỉ 1 log init).
- Xác nhận: Test đã fail (3/3 RED) trước khi sửa, và pass (3/3 GREEN) ngay sau khi sửa.
- Full gate: `.\scripts\ci-local.ps1 -Full` $\rightarrow$ 1,695 tests passed, 38 sanity passed, 93.01% coverage, 0 problem logs.

