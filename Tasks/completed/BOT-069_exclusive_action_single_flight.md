# Nhiệm vụ: `ExclusiveAction` — cơ chế single-flight cho hành động của user

> Thuộc nhóm 6 task cơ chế engine sinh ra từ
> 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — **lớp lỗi D**.
>
> Cặp đôi tự nhiên với [`BOT-067`](BOT-067_resource_scope_lifecycle.md) — xem §2.2.
>
> ## ✅ ĐÃ LÀM
>
> Thiết kế cuối **khác pseudocode ban đầu ở 1 điểm quan trọng**, phát hiện giữa chừng nhờ chạy
> test thật chứ không đoán: `ExclusiveAction` **không wrap `task`** khi nộp cho
> `IThreadManager.submit()` — nó gọi `submit(task, *args, **kwargs)` y hệt như trước, rồi tự
> nhả khoá qua `Future.add_done_callback(...)`. Lý do: bản nháp đầu tiên bọc `task` trong 1
> closure nội bộ trước khi submit — làm vỡ hàng loạt test unit hiện có
> (`test_dashboard_presenter.py`) đang assert trực tiếp `mock_thread_mgr.submit.call_args[0][0]
> == presenter._run_load_history`. Xem §6.1.
>
> Quan hệ FSM/ExclusiveAction (§2.1) chốt theo đúng hướng "phân định rõ": FSM tiếp tục lo
> *hiển thị* (giữ nguyên check `!= UIMode.IDLE` cho `_on_start_stream`, một bất biến khác hẳn —
> "đã LIVE/ERROR" chứ không phải "đang có tác vụ chạy"), `ExclusiveAction` lo *điều phối*
> (thay cờ `historyLoading` viết tay). Không cái nào đá cái nào. Xem §6.2.

## 1. Mục tiêu

[`BOT-027`](BOT-027_fix_concurrent_load_history_race_condition.md) ✅ đã fix
race condition "bấm Load History chồng nhau", nhưng fix là **quy ước, không phải cơ chế**:
cờ `historyLoading` + check FSM viết tay, lặp ở cả `_on_load_history()` lẫn
`_on_start_stream()`
([`stream_lifecycle_controller.py:173-215`](../../src/presentation/ui/screens/dashboard/stream_lifecycle_controller.py#L173)).

Đang chạy đúng và đã có test thật canh. Vấn đề là **entry point thứ 3** thêm vào sau này
sẽ không tự có guard — người viết phải nhớ copy cả 2 đoạn check, và nhớ reset cờ trong
`finally`. Ngoài ra cờ hiện nằm trên ViewModel (`historyLoading`), tức là một khái niệm
điều phối luồng đang sống ở tầng trạng thái-cho-QML.

Mục tiêu: đóng cả lớp `TC-ASY-01`/`03`/`04`/`05` bằng một primitive, thay vì per-handler.

## 2. Thiết kế đề xuất

Ở engine (`sagittarius_engine/`), cạnh `IThreadManager`:

```python
self._load_action = ExclusiveAction(key="load_history", thread_manager=...)
self._load_action.run(self._run_load_history, symbols, interval, ...)
```

Đảm bảo của cơ chế:
- **Tối đa 1 lần chạy đang bay cho mỗi `key`.** Lần gọi thứ 2 khi đang bận → không submit,
  trả về tín hiệu "đang bận" để caller quyết định log gì cho user.
- **Tự nhả trong `finally`**, kể cả khi task ném exception — đây chính là chỗ dễ quên nhất
  khi viết tay.
- **`is_running` quan sát được** để QML bind trực tiếp (`enabled: !action.isRunning`),
  thay cho việc mỗi màn tự nuôi một cờ boolean riêng trên ViewModel.
- **Loại trừ chéo theo nhóm key**: `BOT-027` cho thấy nhu cầu thật không chỉ là "1 nút
  không tự chồng lên chính nó" mà còn là "Load History và Start Live loại trừ lẫn nhau"
  (`TC-ASY-03`). Cần hỗ trợ khai báo nhóm key xung khắc, **không chỉ** khoá theo từng key
  riêng lẻ. Đây là yêu cầu bắt buộc, không phải mở rộng tuỳ chọn.

### 2.1. Chưa chốt — quyết lúc code
Quan hệ với FSM (`BaseStateMachine`). Hôm nay `UIMode.LOCKED` cũng đang làm một phần việc
loại trừ. Hai cơ chế **không được chồng chéo mập mờ**: hoặc `ExclusiveAction` đọc FSM,
hoặc FSM phản ánh `ExclusiveAction`, hoặc phân định rõ FSM lo *hiển thị* còn
`ExclusiveAction` lo *điều phối*. Đọc kỹ `stream_lifecycle_controller.py` rồi chốt —
**đừng để cả hai cùng quyết định và đá nhau**.

### 2.2. Quan hệ với `BOT-067`
Vòng đời của một `ResourceScope` **chính là** vòng đời của một `ExclusiveAction`. Nếu làm
cả hai, `ExclusiveAction` nên là nơi mở/đóng scope, để bất biến "dọn cái cũ trước khi dựng
cái mới" được đảm bảo bởi đúng một chỗ. Nhưng **không ghép thành 1 task** — 2 khái niệm
khác nhau, mỗi cái dùng được độc lập.

## 3. Các bước thực hiện

- [x] `ExclusiveAction` (`sagittarius_engine/runtime/tasks/exclusive_action.py`) + test đơn vị
      dùng **thread thật** (`ThreadManager`/`ThreadPoolExecutor` thật, không mock `submit`) —
      12 test, `tests/runtime/tasks/test_exclusive_action.py`.
- [x] Test: lần 2 khi đang bận bị chặn (cùng key lẫn khác key trong cùng instance); nhả đúng kể
      cả task ném exception; 4 lần gọi dồn dập thật trên thread pool 4 worker chỉ 1 lần được
      chấp nhận, không có overlap thật nào xảy ra.
- [x] Chuyển `stream_lifecycle_controller.py` sang dùng nó, **bỏ** cờ `historyLoading` như
      NGUỒN GATEKEEPING (property `historyLoading` vẫn còn — QML vẫn bind nó để hiện label
      "Loading…"/disable nút Reload trong lúc Load History chạy — nhưng giờ nó chỉ là **tấm
      gương hiển thị**, giá trị của nó không còn được `_on_load_history`/`_on_start_stream`
      đọc lại để quyết định gì nữa. Xem §6.3 vì sao giữ property lại là quyết định đúng, không
      phải nửa vời.).
- [x] Chạy lại nguyên `test_dev_board_async_race_conditions.py` — **4 test gốc xanh không sửa
      1 dòng nào**, cộng 1 test mới cho đúng TC-ASY-03 (chưa từng có test thật trước đây — xem
      §6.4), tổng 5/5.
- [x] Cập nhật 📄 [Test Case Catalog](../reports/dev_board_user_end_test_cases.md) — TC-ASY-01/
      03/04 đổi mô tả cơ chế từ `historyLoading`/FSM sang `ExclusiveAction`, TC-ASY-03 đánh dấu
      lần đầu có test thật thay vì chỉ suy luận thiết kế.

## 4. Rủi ro / Lưu ý

- **Đây là refactor một fix đang chạy đúng, không phải sửa bug.** Rủi ro thuần tuý là làm
  hỏng thứ đang tốt. Tiêu chí thành công: 4 test race hiện có xanh **nguyên xi không sửa**.
- `historyLoading` đang được QML bind trực tiếp — bỏ nó đi thì phải có đường thay thế
  tương đương cho QML, không được để nút mất trạng thái disable.
- Không mở rộng sang các `TC-ASY-*` còn lại (`02`, `09`, `10`, `15`) — khác root cause,
  ngoài phạm vi.

## 5. Phụ thuộc

- 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — nguồn phân tích, lớp D.
- [`BOT-027`](BOT-027_fix_concurrent_load_history_race_condition.md) ✅ — fix viết tay đang thay thế.
- [`BOT-067`](BOT-067_resource_scope_lifecycle.md) — cặp đôi tự nhiên, xem §2.2.
- Sửa `sagittarius_engine/` (repo cha) → commit ở **cả hai** repo.

## 6. Kết quả chi tiết

### 6.1. Thiết kế cuối: 2 pha (`try_start` + `submit`), không wrap `task`

API thật:
```python
if not self._stream_actions.try_start("load_history"):
    ...
    return
# việc trên main thread (ensure_chart_cards/rebuild_scripts) ở giữa
self._stream_actions.submit("load_history", self._run_load_history, symbols, ...)
```

Hai điểm khác pseudocode gốc trong task, cả hai đều bắt buộc bởi ràng buộc thật, không phải
sở thích:

1. **2 pha, không 1 lệnh gộp** — `_ensure_chart_cards`/`_rebuild_scripts()` phải chạy trên main
   thread **giữa** lúc "khoá được chưa" và lúc "nộp cho thread pool" (đã có từ trước, tránh
   race trên `active_indicators`/script set — không phải quyết định mới của task này). Một API
   gộp "kiểm tra rồi nộp luôn" sẽ ép việc main-thread đó ra trước lúc khoá (đá với guard) hoặc
   vào bên trong background task (đá với việc nó phải chạy trên main thread).
2. **`submit()` không wrap `task`** — bản đầu tiên bọc `task` trong 1 closure nội bộ rồi mới
   nộp cho `thread_manager.submit(wrapped)`, tự nhả khoá bằng `try/finally` bên trong wrapper.
   Chạy `tests/unit/presentation/ui/screens/test_dashboard_presenter.py` lộ ngay: nhiều test có
   sẵn assert `mock_thread_mgr.submit.call_args[0][0] == presenter._run_load_history` — với
   wrapper, `submit()` nhận đúng 1 tham số (cái wrapper), không phải `task` thật, nên toàn bộ
   assert kiểu này vỡ dù hành vi thật không hề sai. Sửa bằng
   `Future.add_done_callback(...)` thay cho `try/finally` — `thread_manager.submit(task, *args,
   **kwargs)` giờ nhận đúng y hệt tham số một caller thường nộp, khoá được nhả khi `Future` kết
   thúc (thành công hay lỗi đều tính), verify bằng test riêng
   (`test_submit_passes_task_unwrapped_as_thread_managers_first_positional_arg`) pin chính xác
   thuộc tính này để không ai vô tình bọc lại `task` trong tương lai.

### 6.2. Quan hệ với FSM — 2 bất biến khác nhau, không gộp

`_on_start_stream()` giữ **nguyên** `if self.fsm.current_state != UIMode.IDLE: return` làm
check đầu tiên, tách biệt hoàn toàn với `try_start("start_stream")` theo sau. Lý do xác nhận
qua đọc kỹ code trước khi sửa: check FSM chặn cả case "đã LIVE" và "đang ERROR" — 2 trạng thái
mà `ExclusiveAction` **không biết gì** về (khoá của nó đã được nhả ngay khi
`_run_sync_and_start` kết thúc, bất kể kết thúc thành LIVE hay ERROR). Nếu xoá check FSM và chỉ
dựa vào `ExclusiveAction`, bấm Start Live lần 2 khi **đã đang LIVE** sẽ được chấp nhận lại từ
đầu — một bug hoàn toàn khác, không phải TC-ASY-03. Giữ 2 check tách biệt, thứ tự: FSM trước
(rẻ, không side-effect), `ExclusiveAction` sau (khoá thật).

### 6.3. `historyLoading` property giữ lại — vì sao đúng, không phải nửa vời

Task action item ghi "bỏ cờ `historyLoading` viết tay". Đã verify bằng cách đọc
`DevBoardPanel.qml`: `controlsActive: viewModel.controlsEnabled && !viewModel.historyLoading`
— `historyLoading` **vẫn đang được QML bind trực tiếp** để hiện "Loading…"/khoá nút Reload
riêng cho Load History. Xoá hẳn property sẽ phá QML mà không có gì thay thế — đúng rủi ro task
đã tự cảnh báo ở §4 ("phải có đường thay thế tương đương cho QML"). Quyết định: property ở lại
làm **tấm gương hiển thị** (vẫn `set_history_loading(True/False)` đúng những chỗ cũ), nhưng
**không còn là nguồn quyết định** — `_on_load_history`/`_on_start_stream` không đọc lại nó nữa,
chỉ đọc `ExclusiveAction`. "Bỏ cờ viết tay" đạt được đúng phần quan trọng (gatekeeping logic
không còn là 2 chỗ check tay phải đồng bộ thủ công) mà không phá QML.

Cũng verify: `historyLoading` không cần phản ánh `start_stream` đang chạy — FSM `LOCKED`/`LIVE`
đã tự disable toàn bộ control qua `controlsEnabled` (`DISABLED_UI_MODES = frozenset({"LOCKED",
"LIVE"})`) trong lúc Start Live chạy, nên UI đã đúng mà không cần đụng gì thêm.

### 6.4. TC-ASY-03 lần đầu có test thật

Trước task này, TC-ASY-03 (Load History chồng Start Live) chỉ được XÁC NHẬN qua **đọc code**
(ghi trong task board là "FIXED" nhưng dựa trên suy luận, không có test tự động nào bấm cả 2
nút và kiểm chứng). Test mới
`test_starting_the_live_stream_while_a_history_load_is_in_flight_is_rejected` là test THẬT đầu
tiên cho case này — click Load History (làm chậm dispatch để mở rộng cửa sổ race), rồi bấm
Start Live ngay trong lúc query còn đang "ngủ", verify `StartLiveStreamCommand` chưa từng được
dispatch. Gặp 1 trở ngại thật khi viết: conftest của suite này bật
`DEV_BOARD_AUTOSTART_ENABLED=True`, nên **mở màn hình Dev Board đã tự bấm Start Live một lần**
(`AutoStartController.begin()`, BOT-034) trước khi test kịp làm gì — phải `qtbot.waitUntil` cho
lần tự-start đó ổn định rồi chủ động Stop, đưa FSM về `IDLE` đã biết trước, mới bắt đầu kịch
bản race thật sự muốn test.

### 6.5. Verify cuối

- `sagittarius_engine`'s test suite: 424 pass, 8 skip (413 cũ + 12 test `ExclusiveAction` mới −
  1 trùng đếm), ổn định qua nhiều lần chạy.
- `Sagittarius_Elite_Warrior`'s `tests/unit`+`tests/sanity`: 794 pass (1 test cũ
  `test_timeframe_changed_while_history_loading_does_not_reload` phải sửa lại cách dựng trạng
  thái "đang loading" — dùng `try_start()` thay vì gọi thẳng `set_history_loading(True)`, đúng
  hệ quả của việc chuyển nguồn sự thật, không phải hành vi sai), coverage 93.44%.
- `test_dev_board_async_race_conditions.py`: **5/5 pass**, 4 test gốc không sửa 1 dòng, ổn định
  qua nhiều lần chạy lặp lại (thread thật, đã kiểm tra không flaky).
- Thêm `test_dev_board_custom_scripts.py`/`test_dev_board_indicators.py`/
  `test_dev_board_known_gaps.py`/`test_sanity_ui_e2e.py` — 29/29 pass, xác nhận không phá QML
  binding nào khác trên Dev Board.
- `ruff check`/`format --check` sạch trên mọi file mới/sửa của task này (2 lỗi ruff pre-existing
  gặp phải ở `stream_lifecycle_controller.py`/`test_dashboard_presenter.py` đều nằm ngoài diff
  của task, đã verify bằng `git diff --unified=0`, không đụng).

### 6.6. 2 test fail — điều tra kỹ, xác nhận không liên quan, không tự ý sửa

Lúc chạy rộng hơn `tests/integration/presentation/ui/` để verify, gặp
`test_dashboard_integration.py::test_dashboard_integration_exception_fallback` và
`test_dashboard_live_stream.py::test_dashboard_integration_start_stream_chart_rendering` FAIL.
Nghi ngờ ban đầu (đúng quy trình, không đoán): dùng `git stash` cô lập
`stream_lifecycle_controller.py` về đúng bản TRƯỚC task này, chạy lại 2 test — **fail y hệt**.
Kết luận: **có sẵn từ trước, không liên quan gì đến `ExclusiveAction`**. Đọc kỹ 2 file này xác
định root cause thật (không dừng ở "stash confirm rồi thôi"): cả 2 dùng `mock_dispatch` tự viết
trả `response.data = [mock_kline]` (list phẳng) thay vì `{symbol: [mock_kline]}` — đúng shape
CŨ, từ trước khi PR Bolt "Batch concurrent fetches" đổi `GetHistoricalKlinesQuery.symbol` thành
`str | list[str]` (cùng root cause đã gặp và tự sửa ở fixture của
`test_dev_board_async_race_conditions.py` lúc đóng `BOT-027`, nhưng 2 file này chưa từng được
cập nhật theo). **Không sửa trong task này** — ngoài phạm vi `ExclusiveAction`, thuộc về nợ kỹ
thuật khác. Trong lúc điều tra, một lần chạy khối lớn nhiều file `tests/integration/presentation/ui/`
gộp chung bị crash native (không phải assertion, không có Python traceback) — đúng đặc điểm đã
biết của [`BOT-038`](../backlog/BOT-038_intermittent_segfault_full_ui_integration_suite.md)
("không deterministic theo test hay theo outcome", chỉ xảy ra khi chạy gộp nhiều file); chạy lại
từng file riêng lẻ (như bảng trên) không crash lần nào — đúng cách né đã biết, **không tự ý điều
tra thêm BOT-038** theo đúng ghi chú "không tự ý tiếp tục điều tra nếu chưa được yêu cầu lại"
trong task đó.
