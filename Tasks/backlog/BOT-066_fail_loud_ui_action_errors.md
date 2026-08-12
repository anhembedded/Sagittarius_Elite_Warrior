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

- [ ] Viết test tái hiện trước (đúng [`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md)):
      một slot có `@safe_ui_action` ném `TypeError` — assert hiện tại nó **im lặng**,
      đó là hành vi sai cần đảo.
- [ ] `UiActionFailedEvent` (dataclass, `sagittarius_engine/`) + emit qua `IEventBus`.
- [ ] Log có traceback thay `print()`.
- [ ] Rẽ nhánh dev-mode re-raise theo `DEV_MODE_CONFIG_KEY`.
- [ ] Bật dev-mode trong test suite, **chạy full suite và đếm chính xác bao nhiêu test
      vỡ** — mỗi test vỡ là một lỗi thật đang bị nuốt, phải điều tra từng cái, không
      được tắt cờ đi cho qua.
- [ ] Test: production mode vẫn nuốt (không đổi hành vi ship), dev mode ném lại,
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
