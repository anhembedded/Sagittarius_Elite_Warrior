# Nhiệm vụ: Pre-flight kiểm tra asset UI lúc boot (fail-fast thay vì fallback im lặng)

> Thuộc nhóm 6 task cơ chế engine sinh ra từ
> 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — **lớp lỗi F**.
>
> Mở rộng một cơ chế **đã có sẵn** trong engine, không xây mới từ đầu.

## 1. Mục tiêu

`IconLoader` khi không tìm thấy icon sẽ log `WARNING ... using blank fallback` rồi chạy
tiếp. Hậu quả thật: 7 icon (`sliders`, `chevron-down`, `briefcase`, `save`, `rotate-ccw`,
`shield`, `zap`) biến mất trong một lần `git reset` giữa các lượt merge chồng chéo, app
ship với icon trắng, và **không ai phát hiện** cho tới khi user tự đọc log console dán vào
chat (xem [`BUG-002`](../bug_report/BUG-002.md), dòng 36-40). Phải tới
[`BOT-048`](../completed/BOT-048_migrate_default_scripts_to_inputs.md) mới khôi phục được.

Mục tiêu: asset thiếu phải làm **hỏng boot ở dev**, không phải làm xấu UI ở production.

## 2. Thiết kế đề xuất

Engine **đã có** đúng cơ chế cần thiết, chỉ là chưa áp cho asset UI:
[`DependencyValidatorExtension`](../../../sagittarius_engine/extensions/dependency_validator.py)
— nhận danh sách yêu cầu, kiểm ở `boot()`, thiếu thì log `CRITICAL FAULT` rồi `sys.exit(1)`,
đủ thì log `"Pre-flight check passed"` (dòng này đã xuất hiện trong log của
[`BUG-002`](../bug_report/BUG-002.md)).

Đề xuất: mở rộng khái niệm này sang asset. Hai hướng, **quyết lúc code**:
- Thêm một extension song song (`AssetValidatorExtension`) — tách bạch, không đụng cái đang chạy.
- Hoặc tổng quát hoá `DependencyValidatorExtension` thành nhiều loại "điều kiện pre-flight".
  Sạch hơn về khái niệm nhưng đụng code đang chạy tốt.

Hướng 1 nhiều khả năng đúng hơn (rủi ro thấp hơn, SRP rõ hơn), nhưng đọc code rồi hãy chốt.

### 2.1. Nguồn danh sách asset — điểm cần quyết
Không được hardcode danh sách icon trong engine (engine không biết app dùng icon gì) và
cũng không nên bắt người viết duy trì một danh sách tay (sẽ drift). Ba lựa chọn:
- App khai báo danh sách qua config (`config_keys.py`/`user_config.json`) khi đăng ký extension.
- Quét toàn bộ `.qml`/`.py` tìm tên icon được tham chiếu, đối chiếu với thư mục asset —
  tự động, không drift, nhưng cần parse và có thể có false positive với tên động.
- Ngược lại: quét thư mục asset, assert không rỗng và các icon "core" có mặt — rẻ nhất,
  nhưng bắt được ít nhất.

**Hỏi user nếu phân vân** — đây là đánh đổi giữa công sức và độ phủ, không có đáp án hiển nhiên.

### 2.2. Chỉ fail-fast ở dev mode
Dùng `DEV_MODE_CONFIG_KEY` (`"dev.mode"`, đã có sẵn). Production **không** được `sys.exit`
vì thiếu một cái icon — icon trắng vẫn tốt hơn app không mở được. Ở production giữ nguyên
log warning như hôm nay.

Lưu ý: điều này khác với `DependencyValidatorExtension` hiện tại (luôn `sys.exit(1)`) — hợp
lý, vì thiếu `PySide6` thì app không chạy được thật, còn thiếu icon thì chạy được.

## 3. Các bước thực hiện

- [ ] Chốt nguồn danh sách asset (§2.1) — hỏi user nếu phân vân.
- [ ] Viết test trước: boot app với một asset bị thiếu (dùng thư mục tạm/monkeypatch) →
      assert boot **fail ở dev mode** và assert boot **vẫn qua ở production mode**.
- [ ] Extension + đăng ký trong `binance_bot_module.py`.
- [ ] Verify: xoá thử 1 icon thật → boot dev fail với thông điệp chỉ đúng tên icon và
      đúng đường dẫn nó tìm (giống format thông điệp `CRITICAL FAULT` đang có).
- [ ] Chạy full suite — boot ở test có thể đang chạy dev mode (liên quan
      [`BOT-066`](../completed/BOT-066_fail_loud_ui_action_errors.md)); nếu có asset nào đang thiếu sẵn,
      test sẽ đỏ. Đó là kết quả đúng, điều tra từng cái.

## 4. Rủi ro / Lưu ý

- **Không làm boot chậm đáng kể.** Kiểm tra sự tồn tại của file là I/O; nếu chọn hướng
  "quét toàn bộ `.qml`" ở §2.1 thì phải đo thời gian boot trước/sau.
- Engine là framework dùng chung — extension không được biết gì về `IconLoader` cụ thể của
  app này, chỉ nhận danh sách đường dẫn/điều kiện.
- Không mở rộng sang validate **nội dung** asset (SVG hợp lệ hay không) — ngoài phạm vi,
  và fallback cho SVG hỏng là chuyện khác với SVG không tồn tại.

## 5. Phụ thuộc

- 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — nguồn phân tích, lớp F.
- 📄 [`BUG-002`](../bug_report/BUG-002.md) — log gốc có 5 dòng `Icon not found`.
- [`BOT-048`](../completed/BOT-048_migrate_default_scripts_to_inputs.md) ✅ — nơi 7 icon được khôi phục.
- Sửa `sagittarius_engine/` (repo cha) → commit ở **cả hai** repo.
