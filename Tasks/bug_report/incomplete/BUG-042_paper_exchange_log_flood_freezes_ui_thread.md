# BUG-042 — Backtest nhiều trade làm đơ cứng UI: `PaperExchange` log INFO mỗi lệnh khớp, đổ thẳng vào `LogListModel` trên UI thread

**Trạng thái:** 🔴 Chưa sửa — nguyên nhân đã xác minh thật (code + log thật), fix chưa làm
(user yêu cầu tách riêng, sẽ giao phiên khác)
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
ở màn hình hoàn toàn khác. Đây mới là lỗi kiến trúc thật sự: bất kỳ subsystem nào lỡ log nhiều
đều đơ UI, không riêng gì backtest.

[`signal_log_handler.py:31`](../../../src/presentation/ui/screens/data_management/signal_log_handler.py):

```python
def emit(self, record: logging.LogRecord) -> None:
    self.signal.emit(self.format(record))   # queued cross-thread -> UI thread
```

Backtest chạy trên `IThreadManager` pool (`backtest_presenter.py:911`), nên mỗi `emit` là một
**queued cross-thread signal** xếp hàng sang UI thread.

### 2.3 Đích: mỗi dòng log = 1 chu kỳ cập nhật model trên UI thread

`ui_log_signal` → `_append_log` ([`data_management_presenter.py:299`](../../../src/presentation/ui/screens/data_management/data_management_presenter.py))
→ `LogListModel.append()`
([`log_list_model.py:79`](../../../../Sagittarius_Engine/sagittarius_engine/extensions/pyside_mvc/runtime/log_list_model.py)):

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

Đơ tuyến tính theo số trade: backtest 10.000 trade sẽ đơ ~24 giây.

## 3. KHÔNG phải do `EPIC-006` / xoá native chart

Đã kiểm tra và loại trừ bằng code thật:

- Backtest vẫn submit vào thread pool đúng cách (`backtest_presenter.py:911`) — không chạy trên UI thread.
- Throttle progress của [`BUG-033`](../completed/BUG-033_realtime_backtest_progress_flood_freezes_ui_thread.md)
  (`ProgressThrottle`) vẫn còn nguyên ở cả 2 handler — đường progress **không** phải thủ phạm lần này.
- Handler progress trên UI thread chỉ set property ViewModel, rất nhẹ.
- Không có `processEvents`/`sleep`/`join` nào trong `screens/backtest/` hay `chart_card/`.
- Diff commit `36f3a9f` (xoá native chart) chỉ bỏ nhánh native-fallback, không đụng threading/render path.

Đây là lỗi **có sẵn từ trước**, cùng họ với `BUG-033` (progress flood) nhưng **khác đường dẫn**:
`BUG-033` đi qua signal progress và đã được throttle; `BUG-042` đi qua **đường logging**, chưa
ai chặn.

## 4. Fix đề xuất (chưa làm) — nên sửa cả 2 tầng

Hai lỗi độc lập, sửa 1 tầng không đóng được tầng kia:

1. **Tầng nguồn — `PaperExchange`:** hạ 3 dòng per-fill từ `logger.info` xuống `logger.debug`.
   838×3 dòng không phải thông tin user cần realtime; ở `--dev`/`--debug` vẫn xem đủ.
   *Chỉ sửa tầng này là băng dán* — subsystem khác log nhiều vẫn đơ UI y hệt.

2. **Tầng kiến trúc — `SignalLogHandler`:** không nên bắt toàn bộ logger gốc `"App"` ở INFO.
   Cần chọn 1 trong 2 hướng (quyết định thiết kế, không phải fix 1 dòng):
   - Giới hạn phạm vi: chỉ gắn vào các logger con mà màn Data Management thật sự quan tâm; hoặc
   - Chặn dòng chảy: coalesce/throttle theo thời gian trước khi đẩy sang UI (cùng tinh thần
     `ProgressThrottle` của `BUG-033`), + batch insert cho `LogListModel` thay vì
     `beginInsertRows` từng dòng một.

**Regression test bắt buộc** (theo [`bug-fix-rule.md`](../../../.agents/rules/bug-fix-rule.md) §6 —
phải fail đúng lý do trước khi sửa): chạy một backtest sinh N trade lớn, assert số lần
`LogListModel.append` (hoặc số record tới `SignalLogHandler`) bị chặn trên, **không** tỉ lệ
thuận với số trade.

## 5. Việc còn mở, chưa chẩn đoán được

User báo thêm: sau khi đổi execution mode sang `HISTORICAL_TICK` (log lúc 19:10:41,574) thì
**không chạy được backtest** nữa — log không có dòng backtest nào sau mốc đó cho tới lúc tắt app.

**Chưa kết luận được.** App chạy **không có `--dev`**, nên toàn bộ trace phía Presenter
(`run_submit_start`, `run_worker_submitted`, `coverage_missing`) không được ghi — đúng chỗ cần
nhìn thì trống. Cần chạy lại `python main.py --dev` và lấy `logs/dev-*.log` mới điều tra tiếp
được. Nhiều khả năng là vấn đề **riêng**, không cùng gốc với mục 2 ở trên — đừng gộp.
