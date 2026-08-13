# Nhiệm vụ: Fix Race Condition khi bấm "Load History" nhiều lần liên tiếp

## ✅ Kết quả đóng task

Đã fix — nhưng **không phải trong lần đóng task này**. Điều tra trước khi sửa (đúng quy trình
`.agents/rules/code-rule.md`) phát hiện fix đã nằm sẵn trong code từ một commit không gắn mã task,
`22166fa fix(ui): prevent concurrent history loads`, ra đời cùng lúc `DashboardPresenter` được tách
thành `StreamLifecycleController` (`BOT-037` Phase 2). Xác nhận qua cả code lẫn test thật:

- `StreamLifecycleController._on_load_history()` và `._on_start_stream()` đều check
  `self._view_model.historyLoading` **và** `self.fsm.current_state` ngay đầu hàm, trả về sớm nếu
  có tác vụ nền khác đang chạy — đúng "Hướng nhanh" mà task này đề xuất, áp dụng cho **cả 2** entry
  point (không chỉ Load History), nên `TC-ASY-03` (Load History chồng Start Live) cũng được chặn.
- `test_dev_board_async_race_conditions.py`: 4 test pass, **0 xfail** — 2 test từng `xfail` đã đổi
  tên (`..._corrupt_indicator_series` → `..._keep_indicator_series_correct`) và hết `xfail`, cộng
  thêm `test_load_history_button_is_disabled_during_background_load` mới xác nhận đúng cơ chế
  disable button.

Rà theo đúng 5 action item gốc bên dưới:
- [x] Hướng nhanh (disable trong lúc chạy nền) — đã có, xem trên.
- [x] Hướng cấu trúc (snapshot tham số thay vì đọc lại instance attribute) — không cần nữa, vì
      guard chặn hoàn toàn việc 2 tác vụ nền chạy chồng nhau (không còn 2 lần đọc cùng lúc để đối
      chiếu snapshot vs instance attribute).
- [x] Gỡ `xfail` khỏi 2 test — đã gỡ (tên test cũng đã đổi).
- [x] Cập nhật [Test Case Catalog](../reports/dev_board_user_end_test_cases.md) đánh dấu
      `TC-ASY-01`/`TC-ASY-04` đã fix — bổ sung trong lần đóng task này (kèm `TC-ASY-03`, cùng root
      cause nên cập nhật luôn cho nhất quán).
- [x] Rà `_on_start_stream()` — đã có cùng guard, xem trên.

Không có dòng code nguồn nào bị đổi khi đóng task này — thuần cập nhật tài liệu (báo cáo test case
+ Kanban board) cho khớp thực tế đã fix từ trước.

---

## 1. Mục tiêu (Objective)
Loại bỏ race condition đã **xác nhận tái hiện được bằng test thật** (không chỉ suy đoán): bấm "Load History" 2 lần trở lên trước khi lần trước chạy xong khiến dữ liệu nến bị feed nhiều lần vào cùng 1 bộ indicator (`RSI`/`EMA`/`MACD`), làm sai số liệu hiển thị trên chart.

## 2. Bối cảnh (Context)
Phát sinh từ phiên phân tích **User-End Test Case** cho Dev Board (📄 [`Tasks/reports/dev_board_user_end_test_cases.md`](../reports/dev_board_user_end_test_cases.md), mục D — Async/Race Condition). Hai test case trong đó (`TC-ASY-01`, `TC-ASY-04`) đã được viết thành automated test thật ở `Sagittarius_Elite_Warrior/tests/integration/presentation/ui/test_dev_board_async_race_conditions.py` và **XFAIL đúng như dự đoán** — tức là bug này có thật trên code hiện tại, không phải lý thuyết.

**Root cause đã xác định chính xác:**
- `DashboardPresenter._run_load_history`/`_compute_indicator_series` đọc `self.active_indicators` **tại thời điểm background thread chạy tới đó**, không phải tại thời điểm `_on_load_history()` submit task.
- `IThreadManager` là `ThreadPoolExecutor(max_workers=4)` thật (`sagittarius_engine/infrastructure/thread_manager.py`) — 2-4 lần click liên tiếp có thể chạy **song song thật sự**.
- `load_history_button` **không** bị disable trong lúc đang chạy nền (khác với `start_stream_button`/`stop_stream_button` được khoá qua FSM `LOCKED`) — đây là cửa mở duy nhất cho phép user click chồng.
- Hệ quả: 2 background task cuối cùng cùng đọc **cùng 1 object** `self.active_indicators` (vì lần click sau đã gán đè lên main thread trước khi task nào kịp đọc xong), khiến cùng bộ dữ liệu nến bị `indicator.update()` 2 lần → giá trị RSI/EMA/MACD sai (không phải chỉ lỗi hiển thị, mà sai cả số liệu).

## 3. Các bước thực hiện (Action Items)
Chọn 1 trong 2 hướng dưới đây (đã phân tích sẵn trong report, phần "Tổng kết & đề xuất hành động"):

- [ ] **Hướng nhanh (khuyến nghị làm trước)**: disable `load_history_button` ngay khi bắt đầu chạy nền, enable lại khi `ui_history_reloaded_signal` (hoặc lỗi) trả về — giống hệt cơ chế đã có sẵn cho `start_stream_button` qua FSM `LOCKED`. Chặn được toàn bộ `TC-ASY-01`/`TC-ASY-02`/`TC-ASY-04`/`TC-ASY-05` ngay lập tức, không cần đổi kiến trúc.
- [ ] **Hướng cấu trúc (fix root cause triệt để hơn)**: truyền `active_indicators` như một tham số thật vào `_run_load_history`/`_compute_indicator_series` (chụp snapshot ngay tại thời điểm click, trước khi submit) thay vì đọc lại biến instance `self.active_indicators` dùng chung — loại bỏ hoàn toàn khả năng 2 lần click "nhìn thấy" cùng 1 object.
- [ ] Gỡ `@pytest.mark.xfail(strict=True, ...)` khỏi `test_concurrent_load_history_clicks_corrupt_indicator_series` và `test_four_concurrent_load_history_clicks_corrupt_indicator_series` trong `test_dev_board_async_race_conditions.py` sau khi fix — `strict=True` sẽ tự báo lỗi cứng (XPASS) nếu quên bước này.
- [ ] Cập nhật `Tasks/reports/dev_board_user_end_test_cases.md` — đánh dấu `TC-ASY-01`/`TC-ASY-04` đã fix, xoá khỏi danh sách "Ưu tiên fix trước" ở mục Tổng kết.
- [ ] Rà lại `_on_start_stream()` — nó gọi cùng pattern `_clear_registered_indicators()` + `self.active_indicators = self._build_active_indicators()` trước khi submit `_run_sync_and_start`, nên chịu race tương tự (`TC-ASY-03`) — áp dụng cùng 1 fix cho cả 2 entry point, không chỉ riêng Load History.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Nếu chọn hướng "disable button", cần quyết định thông báo gì cho user trong lúc nút bị khoá (hiện `start_stream_button` không có spinner/label báo "đang tải" — nên xem xét thêm luôn cho nhất quán, dù không bắt buộc để fix race).
- `TC-ASY-03` (Load History rồi Start Live chồng nhau) dùng 2 entry point khác nhau (`_on_load_history` và `_on_start_stream`) — hướng fix cần bao trùm cả 2, không chỉ riêng 1 nút.
- Không mở rộng sang việc wire Symbol/Timeframe dropdown (`TC-GAP-*`, `TC-TF-*`) — đó là phạm vi khác, chưa có yêu cầu triển khai.

## 5. Phụ thuộc (Dependencies)
- `BOT-020` ✅ (Indicator & Strategy Engine Core) — `active_indicators`/`RSI`/`EMA`/`MACD` là những gì đang bị race.
- 📄 [`Tasks/reports/dev_board_user_end_test_cases.md`](../reports/dev_board_user_end_test_cases.md) — nguồn phân tích gốc, có đầy đủ 20 test case Async/Race Condition khác (`TC-ASY-02`...`TC-ASY-20`) nên rà thêm sau khi fix xong 2 case chính này.
- `Sagittarius_Elite_Warrior/tests/integration/presentation/ui/test_dev_board_async_race_conditions.py` — bộ test tái hiện, dùng để verify fix.
