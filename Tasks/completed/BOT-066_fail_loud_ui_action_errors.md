# Nhiệm vụ: `safe_ui_action` phải báo lỗi thật, không nuốt im lặng

> Thuộc nhóm 6 task cơ chế engine sinh ra từ
> 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — **lớp lỗi B**.
>
> **Làm task này TRƯỚC** 5 task còn lại (`BOT-067`…`BOT-071`). Không phải vì nó
> quan trọng nhất, mà vì nó gần như miễn phí và nó biến mọi lớp lỗi còn lại thành
> lỗi **kêu to**. Chừng nào 45 điểm `safe_ui_action` còn nuốt lỗi, cơ chế mới nào
> thêm vào cũng có thể hỏng âm thầm đúng kiểu `BOT-061` đã hỏng.

## 1. Mục tiêu

`safe_ui_action` ([`sagittarius_engine/extensions/pyside_mvc/thread_bridge.py`](../../../sagittarius_engine/extensions/pyside_mvc/thread_bridge.py))
hiện bắt `Exception`, `print()` ra stdout, thử emit `ui_log_signal` bằng duck-typing,
rồi `return None`. Comment trong chính file thừa nhận: *"for now we just swallow to
prevent crash"*.

Nó **không phải lưới an toàn — nó là cái giảm thanh**, đang đặt trên **45 điểm** trong
`Sagittarius_Elite_Warrior/src/`.

Bằng chứng hậu quả thật: ở `BOT-061`, `TypeError` từ `dict(QJSValue)` đi thẳng vào đây
và biến mất. App không sập, nút "Lưu" trông như đã chạy, nhưng **mọi giá trị user gõ
bị vứt bỏ**. Bug sống sót qua nhiều phiên tới khi user tự đọc log console.

Mục tiêu: giữ nguyên tác dụng "không để exception làm sập Qt event loop" ở production,
nhưng lỗi phải **quan sát được** (log có traceback + event có cấu trúc) và ở dev/test
phải **ném lại**.

## 2. Thiết kế đề xuất

Ba thay đổi, độc lập nhau, làm được từng cái một:

### 2.1. Log thật thay cho `print()`
Engine đã có `ILogger` (`sagittarius_engine/interfaces/i_logger.py`, có `error(msg, extra)`).
Dùng `logger.error(...)` kèm **traceback đầy đủ** (`traceback.format_exc()`), không phải
mỗi `str(e)` — `BOT-061` mất một vòng điều tra sai hướng vì thông điệp lỗi quá cụt.

Vấn đề cần giải: decorator là hàm tự do, không có sẵn container để resolve `ILogger`.
Hai hướng, **chọn lúc code**, đừng chốt trước khi đọc call-site thật:
- Duck-typing tiếp `args[0]` (đa số call-site là method của `BasePresenter`, vốn đã có
  `self.logger`) — rẻ, nhưng vẫn là duck-typing.
- Hoặc để `BasePresenter` cung cấp một hook chuẩn (vd. `_report_ui_error(...)`) và
  decorator chỉ gọi hook đó, fallback `print` khi không có. Rõ ràng hơn về hợp đồng.

### 2.2. Phát `UiActionFailedEvent` có cấu trúc
Emit qua `IEventBus` (dataclass event, kế thừa `sagittarius_engine/domain/base_event.py`)
mang: tên hàm, loại exception, thông điệp, traceback. Lý do: **lỗi trở nên test được**.
Hôm nay muốn viết test "hành động này không được nuốt lỗi" thì phải đi bắt stdout —
với event thì chỉ cần subscribe.

### 2.3. Ném lại khi dev mode bật
Rẽ nhánh theo `DEV_MODE_CONFIG_KEY` (`"dev.mode"`, đã có sẵn ở
[`base_view.py:9`](../../../sagittarius_engine/extensions/pyside_mvc/base_view.py#L9),
`BasePresenter` đã đọc nó cho dev-click-logging — **không phát minh cờ mới**).

Bật → `raise` lại sau khi đã log/emit. Tắt → giữ nguyên hành vi nuốt như hôm nay.

**Quan trọng:** test suite phải chạy ở chế độ ném lại, nếu không thì task này vô nghĩa.
Cần xác định cách bật cờ trong `tests/conftest.py` mà không phá 774 test hiện có —
**đây là rủi ro chính của task**, xem §4.

## 3. Các bước thực hiện

- [x] Viết test tái hiện trước (đúng [`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md)):
      một slot có `@safe_ui_action` ném `TypeError` — assert hiện tại nó **im lặng**,
      đó là hành vi sai cần đảo.
- [x] `UiActionFailedEvent` (dataclass, `sagittarius_engine/`) + emit qua `IEventBus`.
- [x] Log có traceback thay `print()`.
- [x] Rẽ nhánh dev-mode re-raise theo `DEV_MODE_CONFIG_KEY`.
- [x] Bật dev-mode trong test suite, **chạy full suite và đếm chính xác bao nhiêu test
      vỡ** — mỗi test vỡ là một lỗi thật đang bị nuốt, phải điều tra từng cái, không
      được tắt cờ đi cho qua.
- [x] Test: production mode vẫn nuốt (không đổi hành vi ship), dev mode ném lại,
      event được phát đúng nội dung ở cả hai chế độ.

## 4. Rủi ro / Lưu ý

- **Rủi ro chính**: bật re-raise trong test suite có thể làm vỡ hàng loạt test đang
  xanh giả nhờ lỗi bị nuốt. Đó là **kết quả tốt** (đúng mục đích task) nhưng có thể
  làm task phình to ngoài dự kiến. Nếu số test vỡ lớn, **dừng lại báo user** trước khi
  sửa hàng loạt — đừng tự ý mở rộng phạm vi.
- Engine là framework dùng chung, không chỉ phục vụ app này. Mặc định (không bật cờ)
  **bắt buộc** giữ nguyên hành vi cũ.
- Không đổi chữ ký `safe_ui_action` (vẫn dùng được dạng `@safe_ui_action` trần) — 45
  call-site không được phép phải sửa theo.

## 5. Phụ thuộc

- 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — nguồn phân tích, lớp B.
- [`BOT-061`](../completed/BOT-061_bot_params_save_qjsvalue_crash.md) ✅ — ca bug thật đã
  chứng minh hậu quả của việc nuốt lỗi.
- Sửa `sagittarius_engine/` (repo cha) → commit ở **cả hai** repo.

## 6. Kết quả triển khai thực tế

**Cơ chế** (`sagittarius_engine/extensions/pyside_mvc/thread_bridge.py`): giữ nguyên chữ
ký `@safe_ui_action` trần (36 call-site hiện tại không đổi 1 dòng). `wrapper` giờ:
1. Log qua `owner.logger.error(msg, extra={"traceback": tb})` (duck-type `args[0]`, đa số
   call-site là `BasePresenter` nên luôn có `self.logger`) — fallback `print()` kèm traceback
   khi không có logger (vd hàm trần không có `self`), thay vì chỉ `str(e)` cụt như trước
   (đúng bài học từ `BOT-061`).
2. Emit `UiActionFailedEvent` (dataclass mới, `ui_action_events.py`) qua `owner.event_bus`
   nếu có — mang `function_name`/`exception_type`/`message`/`traceback`.
3. Vẫn giữ `ui_log_signal` duck-type cũ (back-compat).
4. Rẽ nhánh: `owner.config.get(DEV_MODE_CONFIG_KEY, False)` → `True` thì `raise` lại
   **sau khi** đã log/emit; mặc định (không có cờ, hoặc cờ tắt) giữ nguyên hành vi nuốt
   như hôm nay — không đổi gì cho production.

**7 test engine mới** (`tests/extensions/pyside_mvc/test_thread_bridge.py`, dùng `Mock()`
làm owner, không cần `QApplication`): dev-mode ném lại (test đầu tiên, fail trước fix
đúng như dự kiến), production mode vẫn nuốt, log có traceback, event phát đúng nội dung
ở cả 2 chế độ, `ui_log_signal` vẫn hoạt động, fallback `print()` khi không có owner.

**Bật dev-mode toàn bộ test suite của app** — đúng 4 file test có `@safe_ui_action` thật
(`test_backtest_presenter.py`/`test_dashboard_presenter.py`/`test_settings_presenter.py`/
`test_data_management_presenter.py`), sửa `mock_config`'s `.get` thành key-aware (trả
`True` cho `DEV_MODE_CONFIG_KEY`, giữ nguyên hành vi cũ cho key khác). Kết quả: **9 test
vỡ thật** trên tổng 775 (không phải "lớn" theo ngưỡng task tự đặt ra, nên **không dừng lại
hỏi user** — điều tra và sửa hết theo đúng bước 3):

- **8 test** cùng 1 lớp bug thật: gọi thẳng method nền (`_run_sync_and_start`/
  `_on_stop_stream`/`_run_single_sync`/`_run_scan_all`...) mà **bỏ qua** bước chuyển FSM
  (`IDLE→LOCKED`/`SYNCING`/`SCANNING`) mà entry point công khai (`_on_start_stream()`,
  `_on_sync_data()`...) luôn làm trước khi giao việc nền — nên khi handler hoàn tất gọi
  `transition_to(IDLE)`/`transition_to(ERROR)`, FSM vẫn đang ở `IDLE` và **cả 2** transition
  đó đều không hợp lệ từ `IDLE` (chỉ hợp lệ từ `LOCKED`/`LIVE`/`SYNCING`/`SCANNING`) →
  `InvalidStateTransitionError`, trước đây bị `safe_ui_action` nuốt câm lặng. **Không phải
  bug production reachable được** (nút bấm thật luôn qua entry point trước) — sửa đúng
  chỗ: mỗi test tự `presenter.fsm.transition_to(...)` tới đúng state tiền điều kiện trước
  khi gọi thẳng method nền, khớp đúng con đường gọi thật.
- **1 test** (`test_run_single_sync_dispatches_command`) sau khi FSM không còn crash giữa
  chừng, code chạy hết tới cuối lộ ra `_on_sync_complete()` tự gọi tiếp `_on_check_status()`
  (dispatch thêm 1 query nữa) — assertion cũ đọc `mock_dispatcher.dispatch.call_args` (lệnh
  **cuối cùng**) giờ sai vì lệnh cuối là query mới, không phải sync command nữa. Sửa: tìm
  đúng lệnh Sync trong `call_args_list` thay vì giả định nó luôn là lệnh cuối.
- **1 test** (`test_on_load_history_exception_is_caught_by_safe_ui_action`) tự nó **kiểm
  tra đúng hành vi nuốt lỗi** — phải override về production mode tường minh (`config.get.
  side_effect` không đặc cách `DEV_MODE_CONFIG_KEY`) cho riêng test này, vì mục đích của nó
  khác với phần còn lại của file.

775 test toàn `tests/unit/`+`tests/sanity/` pass (1 fail không liên quan có sẵn từ trước —
`test_interactive_shell_wait_for_exit_exception`, đã xác nhận qua `BOT-072`), 390 test
engine (`tests/`) pass, `ruff` sạch cả 2 repo.
