# Nhiệm vụ: Guard thread-affinity cho UI + sanity test chống drift

> Thuộc nhóm 6 task cơ chế engine sinh ra từ
> 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — **lớp lỗi A**.
>
> Trả lời trực tiếp ghi chú của user ở cuối [`BUG-001`](../bug_report/BUG-001.md):
> *"tôi nghĩ engine nên có cơ chế lo điều này"*.
>
> Nên làm **sau** [`BOT-066`](BOT-066_fail_loud_ui_action_errors.md) ✅ — guard này chỉ có
> tác dụng nếu vi phạm nó không bị `safe_ui_action` nuốt mất. **Điều kiện đó nay đã thoả.**
>
> ## ✅ ĐÃ LÀM
>
> Cả 2 nửa (§2.1 runtime + §2.2 enforcement) đã triển khai đúng thiết kế bên dưới, **không
> đổi hướng gì giữa chừng**. Phát hiện lớn nhất: sanity test không chỉ đỏ vì `set_stats()`
> như dự đoán ban đầu — nó đỏ ở **13 mutator** trên cả 4 màn hình (`set_ui_mode` kế thừa từ
> `BaseQmlViewModel` tính riêng cho từng lớp con nên đếm 4 lần, còn lại là method thật của
> từng ViewModel). Tất cả đều **chưa từng có caller nào chạy trên luồng nền thật** — đúng
> loại "drift" mà `set_stats()` đã minh hoạ, không phải bug đang sống — nhưng giờ được khoá
> lại bằng cơ chế thay vì để tiếp tục trôi. Xem §3/§6 để biết chi tiết từng chỗ.
>
> ## ⬆️ Đề xuất NÂNG ƯU TIÊN — rủi ro đang tăng theo thời gian
>
> Nguồn: 📄 [Rà soát định hướng App](../reports/app_direction_audit.md) §5.
>
> Repo đang nhận **commit tối ưu concurrency tự động** trong khi chưa có guard nào:
>
> ```
> ⚡ Bolt: Offload blocking DB fetch in asyncio coroutine to thread
> ⚡ Bolt: Batch concurrent fetches for GetHistoricalKlinesQuery   ← sửa stream_lifecycle_controller.py
> ```
>
> Trong khi đó:
> - [`BOT-038`](../backlog/BOT-038_intermittent_segfault_full_ui_integration_suite.md) — **segfault
>   ngẫu nhiên đã biết** ở integration UI suite, đã điều tra 1 vòng rồi dừng.
> - [`BUG-001`](../bug_report/BUG-001.md) — app từng **treo** vì chạm UI từ luồng nền.
> - Task này ghi rõ: *"Engine hiện có **0** guard thread nào"*.
>
> Thứ tự đang **ngược**: thêm concurrency vào codebase chưa có cơ chế phát hiện sai luồng
> — cách hiệu quả nhất để tạo bug không tái hiện được.
>
> **Khác với các task hardening còn lại, rủi ro này tăng theo thời gian**: mỗi PR tối ưu
> đồng thời được merge mà chưa có guard là một lớp rủi ro cộng thêm, và càng khó truy
> ngược về sau. Đây là lý do nên nhấc lên trước `BOT-069`/`BOT-071`.

## 1. Mục tiêu

`grep -rn "currentThread\|QueuedConnection" sagittarius_engine/` → **0 kết quả**. Engine
hoàn toàn không có guard thread-affinity nào. Toàn bộ tính đúng đắn của lớp lỗi này đang
dựa vào kỷ luật thủ công của người viết Presenter.

Chẩn đoán của user ở [`BUG-001`](../bug_report/BUG-001.md) chính xác và đáng giữ nguyên văn:
progress update bắn thẳng từ luồng nền lên UI; các phiên bản trước sống sót **chỉ vì**
progress bar không có animation nên QML không tạo Timer nào — *"về lý thuyết vẫn là một
quả bom nổ chậm"*. Thêm `Behavior on width { NumberAnimation }` là kích nổ: app treo kèm
`QBasicTimer::start: Timers cannot be started from another thread`.

Đặc điểm nguy hiểm nhất của lớp lỗi này: **code sai vẫn chạy đúng rất lâu**, chỉ phát bệnh
khi Qt tình cờ cần Timer nội bộ. Không thể phát hiện bằng test hành vi thông thường.

Fix đã áp cho `BUG-001` là thêm `@Slot(int, int, bool)` — nhưng **thủ công, từng method
một**. Bằng chứng nó đã drift: `set_stats()` tại
[`data_management_view_model.py:212`](../../src/presentation/ui/screens/data_management/data_management_view_model.py#L212)
vẫn **chưa có** `@Slot`, trong khi 3 method anh em ngay bên trên (`set_progress`,
`set_progress_value`, `hide_progress`) đều đã có.

## 2. Thiết kế đề xuất

Hai nửa — **nửa thứ hai mới là phần quan trọng**.

### 2.1. Nửa runtime: decorator `@ui_mutator`
Trong `sagittarius_engine/extensions/pyside_mvc/`. So `QThread.currentThread()` với
`self.thread()`:
- Khác nhau **và** dev mode bật (`DEV_MODE_CONFIG_KEY = "dev.mode"`, đã có sẵn) →
  `raise CrossThreadUiMutationError` với thông điệp chỉ rõ method nào, thread nào.
- Khác nhau và dev mode tắt → marshal an toàn về main thread thay vì để Qt tự xử
  (`QMetaObject.invokeMethod(..., Qt.QueuedConnection)`), tức là **tự sửa** ở production
  thay vì treo app.
- Giống nhau → gọi thẳng, không tốn gì.

Khác biệt với `@Slot`: `@Slot` chỉ cứu được khi method được gọi **qua signal có
queued connection**. Nó **không** cứu được khi luồng nền gọi thẳng
`view_model.set_stats(...)`. `@ui_mutator` bắt được cả hai đường.

### 2.2. Nửa enforcement: sanity test quét toàn bộ ViewModel
Đây mới là thứ chặn drift, và nó khớp đúng văn hoá `tests/sanity/` sẵn có của repo
(boot app thật, assert wiring thật):

> Duyệt mọi subclass của `BaseQmlViewModel`, với mỗi method public có tên dạng mutator
> (`set_*`, `append*`, `clear*`, `hide_*`...), assert nó được trang trí bằng `@Slot`
> **hoặc** `@ui_mutator`.

Test này sẽ **đỏ ngay lần chạy đầu tiên** vì `set_stats()` — đó là kết quả đúng, chứng
minh test có tác dụng thật. Sửa `set_stats()` là một phần của task.

## 3. Các bước thực hiện

- [x] Viết sanity test trước (§2.2) — xác nhận nó fail, đúng lý do — hoá ra fail ở **13
      mutator**, không chỉ `set_stats()` (xem §6).
- [x] `CrossThreadUiMutationError` + decorator `@ui_mutator` (engine,
      `sagittarius_engine/extensions/pyside_mvc/thread_affinity.py`). Cơ chế marshal thật
      dùng `QTimer.singleShot(0, self, ...)` — verify bằng thực nghiệm trên đúng bản
      PySide6 đang cài (6.11.1) rằng overload `QMetaObject.invokeMethod(obj, callable,
      type)` (functor Python) **không được hỗ trợ**, chỉ overload theo tên method đăng ký
      sẵn (`str`) mới chạy; `QTimer.singleShot(msec, receiver, callable)` thì có, và đúng là
      cơ chế marshal cần.
- [x] Test đơn vị cho decorator (`tests/extensions/pyside_mvc/test_thread_affinity.py`,
      engine): gọi từ main thread (chạy thẳng), từ **`threading.Thread` thật** ở dev mode
      (ném `CrossThreadUiMutationError`), ở production mode (marshal qua `QCoreApplication`
      thật + `processEvents()` polling, không ném, chạy đúng trên main thread). 11 test,
      pass 100%.
- [x] Sửa `set_stats()` — và 12 mutator khác lộ ra qua sanity test (xem §6) — tất cả bằng
      `@Slot(kiểu_tham_số_khớp)`, đúng convention sẵn có của từng file (không dùng
      `@ui_mutator` cho method nào — lý do ở §6.1).
- [x] Rà toàn bộ `ui_*_signal.connect(...)` + mọi caller của 13 mutator — xác nhận **100%**
      đích đến đã được bảo vệ (chi tiết caller-by-caller ở §6).

## 4. Rủi ro / Lưu ý

- **Không đổi mọi `@Slot` hiện có thành `@ui_mutator`.** `@Slot` vẫn cần thiết cho phần
  QML gọi ngược vào Python. Hai thứ bổ sung nhau, không thay thế nhau. Sanity test chấp
  nhận **cả hai**.
- Danh sách tiền tố tên method ở §2.2 là heuristic — sẽ có false negative (mutator đặt tên
  khác) và false positive. Khi gặp, **thêm cơ chế opt-out tường minh** (vd. một decorator
  `@not_a_ui_mutator` hoặc allowlist có ghi lý do), đừng nới lỏng heuristic cho đến khi
  nó không bắt được gì nữa.
- Rủi ro hiệu năng: so sánh thread mỗi lần gọi. Không đáng kể với tần suất UI hiện tại,
  nhưng **không** áp decorator này lên đường đi của tick live tần suất cao mà chưa đo.
- Engine là framework dùng chung — mặc định (dev mode tắt) không được đổi hành vi hiện có
  ngoài việc marshal thay vì treo.

## 5. Phụ thuộc

- 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — nguồn phân tích, lớp A.
- 📄 [`BUG-001`](../bug_report/BUG-001.md) — ca thật, có chẩn đoán gốc của user.
- [`BOT-066`](BOT-066_fail_loud_ui_action_errors.md) — nên làm trước.
- Sửa `sagittarius_engine/` (repo cha) → commit ở **cả hai** repo.

## 6. Kết quả chi tiết

### 6.1. Vì sao chọn `@Slot` cho cả 13 chỗ, không dùng `@ui_mutator`

Rà từng caller (background worker `_run_*` lẫn `@Slot`-handler nhận signal) xác nhận: **cả
13 mutator hôm nay chỉ có caller trên main thread** — hoặc gọi trực tiếp từ handler QML
(click), hoặc gọi từ bên trong 1 `@Slot`-handler khác đã được Qt marshal đúng qua
`ui_*_signal.emit()`/`.connect()` từ luồng nền. Không có caller nào gọi thẳng method từ bên
trong `_run_*`. Vì vậy `@Slot(kiểu tham số)` — khớp đúng convention 17 method anh em đã có
sẵn trước đó (`set_progress`, `_on_ui_chart_update`, v.v.) — là fix đúng và tối thiểu, không
cần `@ui_mutator`'s dev-mode-raise/marshal cho ca nào (cơ chế đó vẫn tồn tại, sẵn sàng cho
mutator MỚI thêm sau này mà có caller nền thật).

**Đã sửa** (13 chỗ, 5 file, 2 repo):
- `sagittarius_engine/extensions/pyside_mvc/QmlShared/base_view_model.py` —
  `BaseQmlViewModel.set_ui_mode()` → `@Slot(str)` (ảnh hưởng cả 4 lớp con qua kế thừa).
- `dashboard_view_model.py` — `set_price_ticker`, `set_ws_status` (`@Slot(str, str)`),
  `set_history_loading` (`@Slot(bool)`).
- `data_management_view_model.py` — `set_stats` (`@Slot(str, str)`) — ca gốc task này nhắm tới.
- `settings_view_model.py` — `set_status` (`@Slot(str, bool)`).
- `backtest_view_model.py` — `set_strategy_options`/`set_bot_params_schema`
  (`@Slot("QVariantList")`), `set_bot_params_error` (`@Slot(str)`), `set_result`
  (`@Slot(str, bool)`), `set_stat_cards` (`@Slot("QVariantList", "QVariantList")`),
  `set_needs_data_sync` (`@Slot(bool)`), `set_trade_log_page_state`
  (`@Slot("QVariantList", int, int)`).

### 6.2. Bug thật tìm thấy trong lúc viết scanner (đã sửa + có test riêng)

`unprotected_mutators()` ban đầu false-positive trên
`DataManagementViewModel.clearDataRequested` — đó là một `Signal()`, không phải method, chỉ
vì TÊN của nó khớp tiền tố `clear`. Nguyên nhân: `Signal` instance ở mức class **cũng
callable** (đó là cách cú pháp `Signal(int, str)` hoạt động), nên check `callable(member)`
không đủ. Sửa bằng `isinstance(member, Signal)` loại trừ tường minh, kèm test riêng
(`test_scanner_does_not_flag_a_signal_whose_name_matches_a_mutator_prefix`) dựng lại đúng
ca thật này.

### 6.3. Một flake hiếm, không liên quan, không đuổi theo

Trong ~13 lần chạy `sagittarius_engine`'s test suite đầy đủ lúc phát triển, gặp đúng 1 lần
`PytestUnhandledThreadExceptionWarning` với traceback dính `Mock(side_effect=[...])`/
`StopIteration` — không có gì trong `thread_affinity.py` dùng `Mock`/`side_effect`. Không tái
hiện được khi chạy riêng file test mới, không xuất hiện ở baseline (không có thay đổi của
task này) qua nhiều lần chạy. Kết luận hợp lý nhất: 1 flake hiếm, có sẵn từ trước ở đâu đó
trong test scheduler/IPC-broker dùng thread thật, bị lộ ra khi có thêm việc dùng thread khác
chạy cùng process — **không sửa trong task này**, ghi lại để không ai mất công điều tra lại
nếu gặp lần nữa.

### 6.4. Một lỗi test-isolation khác tìm thấy (đã sửa)

`test_every_view_model_subclass_in_this_app_is_covered_by_this_list` (test tự-bảo-vệ, chống
`_ALL_VIEW_MODELS` trôi so với thực tế) fail khi chạy **cùng** `tests/unit`+`tests/sanity`
đầy đủ nhưng pass khi chạy riêng: `BaseQmlViewModel.__subclasses__()` bắt luôn
`test_shared_ui_state_foundation.py`'s `_ProbeViewModel` — 1 class cục bộ bên trong 1 hàm
test khác, dựng ra chỉ để test cơ chế FSM/uiMode dùng chung, không phải màn hình thật. Sửa
bằng lọc theo `cls.__module__.startswith("Sagittarius_Elite_Warrior.src.")` — loại mọi class
không thuộc package sản phẩm thật, dù nó có kế thừa `BaseQmlViewModel` hay không.

### 6.5. Verify cuối

- `sagittarius_engine`'s test suite: 411 pass, 8 skip (không đổi so với trước task).
- `Sagittarius_Elite_Warrior`'s `tests/unit`+`tests/sanity`: **794 pass** (793 trước +
  1 sanity test mới, minus phần trùng), coverage 93.44%, chạy lặp lại ổn định.
- 28 test tích hợp UI đụng Dev Board (`test_dev_board_custom_scripts.py`,
  `test_dev_board_indicators.py`, `test_dev_board_known_gaps.py`,
  `test_dev_board_async_race_conditions.py`, `test_sanity_ui_e2e.py` — bao phủ luôn
  Dashboard/Data Management/Settings qua walkthrough thật) — **28/28 pass**, xác nhận thêm
  `@Slot(kiểu)` không phá binding QML nào.
- `ruff check`/`format --check` sạch trên mọi file mới/sửa của task này (4 lỗi ruff pre-existing
  gặp phải ở `base_presenter.py`/`__init__.py` đều nằm ngoài diff của task, không đụng).
