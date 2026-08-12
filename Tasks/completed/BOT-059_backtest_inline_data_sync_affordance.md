# Nhiệm vụ: Backtest Screen — Nút "Đồng bộ ngay" khi thiếu dữ liệu lịch sử

> Thuộc Epic [BOT-040 — Backtest Screen Full Feature Set](BOT-040_backtest_screen_full_feature_epic.md), Nhóm D (nối tiếp `BOT-022`). Phụ thuộc `BOT-022` ✅, khuyến nghị làm sau `BOT-058` (dùng chung symbol/interval mặc định từ config).

## 1. Mục tiêu (Objective)

Backtest là **tính năng chính**, không được phép phụ thuộc ngầm vào việc
user đã lỡ mở Dev Board (hay Data Management) để sync dữ liệu trước đó.
Hiện tại, khi DB chưa có dữ liệu cho symbol/interval/khoảng thời gian đã
chọn, `RunStaticBacktestCommandHandler` trả `None` và màn hình chỉ hiện
dòng chữ tĩnh "Không có dữ liệu lịch sử... Hãy sync dữ liệu trước." — **ngõ
cụt**, user phải tự rời màn hình, đoán ra cần đi đâu để sync (Data
Management), rồi quay lại. Task này thêm 1 nút hành động ngay trong màn
Backtest để tự đóng vòng lặp đó.

**Quyết định UX đã chốt**: **không** tự động sync ngầm khi bấm "Chạy
Backtest" (im lặng gọi API Binance tốn network/rate-limit mà user không biết)
— hiện rõ 1 nút hành động, user **chủ động** bấm mới sync.

**Quyết định kiến trúc đã chốt**: task này thêm việc chạy nền **thứ hai**
(sync, cạnh việc chạy backtest đã có) — thay vì vá thêm 1 cờ `isSyncing:
bool` cạnh `UIMode` dùng chung (Dashboard/Data Management cũng dùng), đổi
hẳn sang 1 state machine riêng cho màn Backtest (`BacktestState`). Xem chi
tiết mục 3.1.

## 2. Mô tả (Description)

`SyncMarketDataCommand` (`src/application/use_cases/sync/sync_market_data/`)
đã có sẵn, đã dùng ở Data Management screen
(`data_management_presenter.py::_run_single_sync`, dòng ~280 — dùng làm mẫu
tham khảo threading, KHÔNG copy nguyên progress-bar/event phức tạp của nó,
Backtest chỉ cần biết xong hay chưa xong):
```python
cmd = SyncMarketDataCommand(
    symbols=[symbol],
    interval=TimeFrame(interval),
    start_time=start_time,
    end_time=end_time,
)
self.dispatcher.dispatch(SyncMarketDataCommand, cmd)  # trả về None, block tới khi xong
```
`execute()` chạy đồng bộ (block hết thời gian gọi Binance + ghi DB), **không**
trả kết quả — biết "xong" bằng việc `dispatch()` return mà không raise. Có
phát `SingleSyncProgressEvent` qua `IEventBus` để vẽ progress bar (Data
Management dùng) — task này **không bắt buộc** phải vẽ progress bar, chỉ
cần trạng thái "đang đồng bộ.../xong" đơn giản (xem mục 5, có thể để task
sau nếu muốn progress bar đẹp).

## 3. Các bước thực hiện (Action Items)

### 3.1 `BacktestState` — thay `UIMode` dùng chung bằng state machine riêng

Đã phát hiện trong lúc chạy thật: `BackTestPresenter` hiện dùng chung
`UIMode` (`IDLE`/`LIVE`/`LOCKED`/`ERROR` — `src/presentation/ui/constants.py`)
với Dashboard/Data Management. Chỉ 1 việc chạy nền (backtest) thì `LOCKED`
dùng tạm được, nhưng task này thêm việc chạy nền **thứ hai** (sync) — nếu cứ
gộp chung `LOCKED` + tự thêm cờ `isSyncing: bool` bên cạnh thì UI không còn
biết "đang khoá vì lý do gì", 2 nguồn trạng thái (`fsm.current_state` +
`isSyncing`) phải tự tay giữ đồng bộ, dễ lệch. Sửa tận gốc thay vì vá thêm:

- [ ] Tạo `src/presentation/ui/screens/backtest/backtest_state.py`:
  ```python
  class BacktestState(str, Enum):
      IDLE = "IDLE"
      RUNNING = "RUNNING"
      SYNCING = "SYNCING"
      ERROR = "ERROR"
  ```
  (`BaseStateMachine`/`BaseQmlViewModel`/`QmlHostView.apply_ui_mode` đã tổng
  quát hoá theo *bất kỳ* enum có `.value` — xem `BasePresenter._bind_fsm_to_ui`,
  `BackTestView.apply_ui_mode` — đổi enum không cần sửa các lớp base này.)
- [ ] `BackTestPresenter`: đổi `INITIAL_STATE = UIMode.IDLE` →
  `BacktestState.IDLE`; đổi toàn bộ `self.fsm.transition_to(UIMode.XXX)` /
  `self.fsm.add_transition(UIMode.A, UIMode.B)` hiện có (`_on_run_backtest`,
  `_on_backtest_succeeded`, `_on_backtest_empty`, `_on_backtest_failed`)
  sang `BacktestState` tương ứng (`LOCKED` cũ → `RUNNING`). Đăng ký thêm
  transition: `IDLE → SYNCING`, `SYNCING → RUNNING` (sync xong, tự chạy lại
  — xem 3.3), `SYNCING → IDLE` (sync lỗi).
- [ ] `BackTestViewModel`: đổi `DISABLED_UI_MODES = frozenset({UIMode.LOCKED.
  value})` → `frozenset({BacktestState.RUNNING.value, BacktestState.SYNCING.
  value})` — cả 2 trạng thái bận đều khoá control, `controlsEnabled` hiện có
  tự động đúng, không cần đổi gì ở QML cho phần đã có.
- [ ] Cập nhật lại toàn bộ test hiện có trong `test_backtest_presenter.py`
  đang so `presenter.fsm.current_state == UIMode.LOCKED` (và tương tự) sang
  `BacktestState.RUNNING`.

### 3.2 Phân biệt "thiếu dữ liệu" và "0 trade"

- [ ] `BackTestViewModel`: thêm `needsDataSync: bool` (đọc, Python ghi) +
  `syncRequested = Signal()` (QML gọi qua `requestSync()` Slot, giống
  `runBacktestRequested`/`requestRun()` đã có). **Không** cần `isSyncing`
  riêng nữa — QML đọc thẳng `viewModel.uiMode === "SYNCING"`.
- [ ] `BackTestPresenter`: cache `self._last_no_data_config:
  BacktestRunConfig | None`, set mỗi lần *thật sự* thiếu dữ liệu.
- [ ] **Phải tách 2 nhánh** hiện đang gộp chung trong `_run_backtest`:
    - "Không có dữ liệu lịch sử" (`result is None`) → set `needsDataSync =
      True`, cache config, **KHÔNG** còn dùng chung message với ca dưới.
    - "0 trade nhưng có dữ liệu" (`result` không `None`, `result.trades`
      rỗng) → `needsDataSync = False` — đây vẫn là kết quả hợp lệ, không
      phải thiếu dữ liệu.
  (Có thể cần 2 signal riêng thay vì gộp `_backtestEmptySignal` như hiện tại,
  hoặc thêm tham số phân biệt — tuỳ người implement chọn cách rõ ràng nhất,
  miễn giữ đúng phân biệt này.)

### 3.3 Luồng sync

- [ ] `_on_request_sync` (slot mới, nối `view_model.syncRequested`): guard
  bỏ qua nếu `self._last_no_data_config is None` hoặc
  `self.fsm.current_state != BacktestState.IDLE`. Transition
  `IDLE → SYNCING`, `self._thread_manager.submit(self._run_sync,
  self._last_no_data_config)`.
- [ ] `_run_sync` (method nền mới, submit qua `IThreadManager`, **chỉ được
  emit signal, không đụng ViewModel/FSM trực tiếp** — đúng threading
  contract của `_run_backtest`): dispatch `SyncMarketDataCommand` với đúng
  symbol/interval/`start_time`/`end_time` từ config đã cache; try/except
  quanh dispatch, emit `_syncSucceededSignal`/`_syncFailedSignal(message)`.
- [ ] Khi sync thành công (main thread): `needsDataSync = False`, cập nhật
  `resultText` báo đã đồng bộ xong, transition `SYNCING → RUNNING`, rồi
  **tự động submit lại `_run_backtest`** 1 lần với cấu hình hiện tại của
  toolbar (không phải config đã cache — user có thể đã đổi field khác trong
  lúc chờ sync). Quyết định: **tự chạy lại** vì user đã bấm "Chạy Backtest"
  1 lần rồi — sync chỉ là bước điều kiện tiên quyết được chèn vào, không
  phải 1 hành động user yêu cầu độc lập. Nếu thấy tự động chạy lại gây khó
  hiểu khi implement, ghi rõ lý do đổi quyết định trong PR thay vì tự ý âm
  thầm bỏ qua bước này.
- [ ] Khi sync lỗi: transition `SYNCING → IDLE`, `needsDataSync` giữ `True`
  (cho phép bấm lại), hiện lỗi trong `resultText`.
- [ ] `BackTestTopPanel.qml`: trong nhánh hiển thị khi `primaryStatCards`
  rỗng (khu vực `txtBacktestResult` hiện có), thêm 1 `Button` "Đồng bộ ngay"
  — chỉ `visible` khi `viewModel.needsDataSync`, `enabled: viewModel.uiMode
  !== "SYNCING"`, text đổi thành "Đang đồng bộ..." khi `viewModel.uiMode ===
  "SYNCING"`, `onClicked: viewModel.requestSync()`.
- [ ] Unit test: ca thiếu dữ liệu → `needsDataSync` bật, bấm
  `requestSync()` → FSM sang `SYNCING`, `mock_thread_mgr.submit` gọi đúng
  `_run_sync` với đúng config đã cache; `_run_sync` dispatch đúng
  `SyncMarketDataCommand`; sync thành công → FSM `SYNCING → RUNNING`,
  `needsDataSync` tắt, `RunStaticBacktestCommand` được dispatch lại lần 2 tự
  động; sync lỗi → FSM `SYNCING → IDLE`, `needsDataSync` vẫn bật, lỗi hiện
  đúng chỗ. Ca "0 trade" (có dữ liệu, chỉ là không khớp lệnh) →
  `needsDataSync` **không** bật (guard test riêng, tránh tái phạm việc gộp
  nhầm 2 nhánh).

## 4. Rủi ro / Lưu ý (Constraints & Risks)

- Mục 3.1 đụng vào code **đã ship** của `BOT-022` (`INITIAL_STATE`, mọi
  `fsm.transition_to`, `DISABLED_UI_MODES`) — đổi tên/giá trị enum, không
  đổi hành vi (`RUNNING` thay thế đúng vị trí `LOCKED` cũ). Chạy lại toàn bộ
  test suite hiện có của `test_backtest_presenter.py` sau khi đổi, không chỉ
  test mới thêm ở task này.
- **Không** tự sync khi user chưa từng bấm "Chạy Backtest" — nút chỉ xuất
  hiện *sau khi* 1 lần chạy thất bại vì thiếu dữ liệu, không hiện sẵn từ đầu
  (tránh mời gọi sync tốn network mà chưa chắc user cần chạy backtest ngay).
- `SyncMarketDataCommand.execute()` là lệnh gọi mạng thật tới Binance — có
  thể mất vài giây tới vài chục giây tuỳ khoảng thời gian; trạng thái
  `SYNCING` phải khoá cả nút "Đồng bộ ngay" lẫn "Chạy Backtest" (tái dùng
  `viewModel.controlsEnabled` đã tự đúng sau khi sửa `DISABLED_UI_MODES` ở
  3.1) tránh bấm chồng.
- Không vẽ progress bar chi tiết (`SingleSyncProgressEvent`) ở task này —
  1 trạng thái "đang đồng bộ..." đơn giản là đủ; nếu sau này cần progress
  bar đẹp như Data Management, tách task riêng.

## 5. Phụ thuộc

- `BOT-022` ✅ — khung màn hình, FSM, `_run_backtest`.
- `BOT-058` — khuyến nghị làm trước, để symbol/interval mặc định đã đúng
  nguồn config trước khi thêm luồng sync (tránh sync nhầm giá trị hardcode
  cũ nếu làm ngược thứ tự — không bắt buộc chặn cứng, chỉ khuyến nghị).
